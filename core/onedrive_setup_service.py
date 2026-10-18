"""Personal OneDrive setup only: no scans, writes to Graph, or transfers."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from core.onedrive_auth import OneDriveAuth, OneDriveTokenStore, OneDriveReconnectRequired
from utils.settings import SettingsService


class OneDriveSetupError(RuntimeError):
    """Safe, user-facing setup failure."""


@dataclass(frozen=True)
class CloudFolder:
    id: str
    name: str


class OneDriveSetupGateway:
    """Read-only Graph adapter; injectable transport keeps tests offline."""

    ROOT = "https://graph.microsoft.com/v1.0"

    def __init__(self, token, session=None):
        if session is None:
            import requests
            session = requests.Session()
        self._session = session
        self._token = token

    def _get(self, url):
        if not url.startswith(self.ROOT + "/"):
            raise OneDriveSetupError("OneDrive returned an unsupported folder link.")
        try:
            response = self._session.get(
                url, headers={"Authorization": f"Bearer {self._token}"},
                timeout=(15, 45), allow_redirects=False,
            )
            if response.status_code == 401:
                raise OneDriveSetupError("Your connection expired. Connect your account again.")
            if response.status_code != 200:
                raise OneDriveSetupError("OneDrive could not open this folder. Check access and try again.")
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except OneDriveSetupError:
            raise
        except Exception:
            raise OneDriveSetupError("Could not reach OneDrive. Check your connection and try again.") from None

    def identity(self):
        profile = self._get(self.ROOT + "/me?$select=id,displayName,userPrincipalName")
        drive = self._get(self.ROOT + "/me/drive?$select=id,driveType")
        if drive.get("driveType") != "personal":
            raise OneDriveSetupError("This preview supports personal OneDrive accounts only.")
        return profile["id"], profile.get("userPrincipalName") or profile["displayName"], drive["id"]

    def folder(self, drive_id, folder_id="root"):
        resource = "root" if folder_id == "root" else "items/" + quote(folder_id, safe="")
        item = self._get(f"{self.ROOT}/drives/{quote(drive_id, safe='')}/{resource}")
        if "folder" not in item or "remoteItem" in item or "deleted" in item:
            raise OneDriveSetupError("Choose an ordinary folder in your personal OneDrive.")
        return CloudFolder(item["id"], item["name"])

    def children(self, drive_id, folder_id):
        url = f"{self.ROOT}/drives/{quote(drive_id, safe='')}/items/{quote(folder_id, safe='')}/children"
        folders, seen_pages, seen_ids = [], set(), set()
        while url:
            if url in seen_pages:
                raise OneDriveSetupError("OneDrive repeated a folder page. Please reconnect.")
            seen_pages.add(url)
            page = self._get(url)
            for item in page.get("value", []):
                if "folder" in item and "remoteItem" not in item and "deleted" not in item:
                    if item["id"] not in seen_ids:
                        folders.append(CloudFolder(item["id"], item["name"]))
                        seen_ids.add(item["id"])
            url = page.get("@odata.nextLink")
        return sorted(folders, key=lambda folder: (folder.name.casefold(), folder.id))


class OneDriveSetupService:
    """Owns connected identity and saves only folders verified in this session."""

    def __init__(self, auth=None, gateway_factory=OneDriveSetupGateway, settings_service=SettingsService):
        self._auth = auth
        self._gateway_factory = gateway_factory
        self._settings = settings_service
        self._gateway = None
        self.account_id = self.account_name = self.drive_id = ""
        self.root = None
        self._known = {}

    def connect(self):
        self._clear_connection()
        try:
            if self._auth is None:
                self._auth = OneDriveAuth(OneDriveTokenStore())
            token, _result = self._auth.connect()
            gateway = self._gateway_factory(token)
            account_id, account_name, drive_id = gateway.identity()
            root = gateway.folder(drive_id)
            if not all(isinstance(value, str) and value.strip()
                       for value in (account_id, account_name, drive_id, root.id, root.name)):
                raise ValueError()
        except Exception:
            raise OneDriveSetupError(
                "OneDrive could not connect. This preview needs a configured personal-account build; "
                "if already configured, check your connection and try again."
            ) from None
        self._gateway = gateway
        self.account_id, self.account_name, self.drive_id = account_id, account_name, drive_id
        self.root = root
        self._known[root.id] = root
        return root

    def _clear_connection(self):
        self._gateway = None
        self.root = None
        self._known.clear()
        self.account_id = self.account_name = self.drive_id = ""

    def restore_pair(self, name, *, interactive=False):
        """Resolve saved native IDs without enabling comparison or copying."""
        self._clear_connection()
        pair = next((pair for pair in self.saved_pairs() if pair["name"] == name), None)
        if pair is None:
            raise OneDriveSetupError("This saved Folder Pair is no longer available.")
        if not Path(pair["local_folder"]).is_dir():
            raise OneDriveSetupError("The saved local folder is unavailable. Restore access before opening this pair.")
        endpoint = pair["server_endpoint"]
        try:
            if self._auth is None:
                self._auth = OneDriveAuth(OneDriveTokenStore())
            reference = endpoint.get("auth_account_id", "")
            if reference:
                token, _result = self._auth.acquire_for_account(reference, interactive=interactive)
            elif interactive:
                token, _result = self._auth.connect()
            else:
                raise OneDriveReconnectRequired("This older pair needs an explicit reconnect to verify its account.")
            gateway = self._gateway_factory(token)
            account_id, account_name, drive_id = gateway.identity()
            if account_id != endpoint["account_id"] or drive_id != endpoint["drive_id"]:
                raise OneDriveSetupError("The connected account or drive does not match this Folder Pair. Reconnect the saved account.")
            folder = gateway.folder(drive_id, endpoint["folder_id"])
            if folder.id != endpoint["folder_id"]:
                raise OneDriveSetupError("The saved cloud folder changed. Choose the folder again.")
            folders = gateway.children(drive_id, folder.id)
            # Upgrade an older pair's cache reference only after explicit sign-in
            # and independent Graph identity checks. Keep unrelated settings.
            renewed_reference = getattr(self._auth, "account_reference", "")
            if (interactive and isinstance(renewed_reference, str) and renewed_reference
                    and renewed_reference != endpoint.get("auth_account_id")):
                settings = self._settings.load()
                current = next((item for item in settings.get("folder_pairs", [])
                                if item["name"] == name), None)
                if current != pair:
                    raise OneDriveSetupError("The saved pair changed while reconnecting. Open it again.")
                pair = dict(pair, server_endpoint=dict(endpoint, auth_account_id=renewed_reference))
                settings["folder_pairs"] = [pair if item["name"] == name else item
                                            for item in settings["folder_pairs"]]
                self._settings.save(settings)
        except OneDriveReconnectRequired as error:
            raise OneDriveSetupError(str(error)) from None
        except OneDriveSetupError:
            raise
        except Exception:
            raise OneDriveSetupError("Could not reopen this Folder Pair. Check access and reconnect if needed.") from None
        self._gateway = gateway
        self.account_id, self.account_name, self.drive_id = account_id, account_name, drive_id
        self.root = folder
        self._known = {item.id: item for item in [folder, *folders]}
        return pair, folder, folders

    def disconnect_pair(self, name):
        self._clear_connection()
        pair = next((pair for pair in self.saved_pairs() if pair["name"] == name), None)
        if pair is None:
            raise OneDriveSetupError("Choose a saved Folder Pair first.")
        try:
            if self._auth is None:
                self._auth = OneDriveAuth(OneDriveTokenStore())
            self._auth.forget_account(pair["server_endpoint"].get("auth_account_id", ""))
        except OneDriveReconnectRequired as error:
            raise OneDriveSetupError(str(error)) from None
        except Exception:
            raise OneDriveSetupError("The saved sign-in could not be removed. Please try again.") from None

    def prepare_comparison(self, name):
        """Resolve a saved pair afresh, then bind the transport to its exact account."""
        from core.onedrive_provider import OneDriveProvider
        pair, folder, _children = self.restore_pair(name)
        reference = pair["server_endpoint"].get("auth_account_id", "")
        if not reference:
            raise OneDriveSetupError("Reconnect this pair before using it for comparison.")
        auth = self._auth
        def token_supplier():
            return auth.acquire_for_account(reference)[0]
        provider = OneDriveProvider(self.drive_id, folder.id, folder.name, token_supplier,
                                    session=self._gateway._session)
        return pair, provider

    def list_folders(self, folder_id):
        if self._gateway is None or folder_id not in self._known:
            raise OneDriveSetupError("Connect an account and choose a folder first.")
        folders = self._gateway.children(self.drive_id, folder_id)
        self._known.update({folder.id: folder for folder in folders})
        return folders

    def save_pair(self, name, local_folder, folder_id):
        if self._gateway is None or folder_id not in self._known:
            raise OneDriveSetupError("Connect an account and choose a folder first.")
        if not name.strip() or not Path(local_folder).is_dir() or not local_folder.strip():
            raise OneDriveSetupError("Enter a pair name and choose an existing local folder.")
        # Verify selection again before persisting; a deleted/moved account item
        # must not be turned into an apparently ready saved relationship.
        folder = self._gateway.folder(self.drive_id, folder_id)
        if folder.id != folder_id:
            raise OneDriveSetupError("The selected folder changed. Choose it again.")
        settings = self._settings.load()
        pairs = settings.get("folder_pairs", [])
        if any(pair["name"].casefold() == name.strip().casefold() for pair in pairs):
            raise OneDriveSetupError("That Folder Pair name is already used. Choose another name.")
        pair = {
            "name": name.strip(), "local_folder": str(Path(local_folder)),
            "server_endpoint": {
                "provider": "onedrive", "account_id": self.account_id,
                "account_name": self.account_name, "drive_id": self.drive_id,
                "folder_id": folder.id, "folder_name": folder.name,
            },
        }
        reference = getattr(self._auth, "account_reference", "")
        if isinstance(reference, str) and reference:
            pair["server_endpoint"]["auth_account_id"] = reference
        updated = dict(settings, folder_pairs=[*pairs, pair])
        self._settings.save(updated)
        return pair

    def saved_pairs(self):
        return [pair for pair in self._settings.load().get("folder_pairs", [])
                if pair.get("server_endpoint", {}).get("provider") == "onedrive"]
