"""Google folder browsing and credential-free named pairs; no remote writes."""
from pathlib import Path

from core.google_drive_auth import GoogleDriveAuth, GoogleOAuthDiagnosticError
from core.google_drive_provider import GoogleDriveProvider
from core.onedrive_setup_service import CloudFolder, OneDriveSetupError
from utils.settings import SettingsService


class GoogleSetupError(OneDriveSetupError):
    """Safe message understood by the shared folder-pair presentation."""


class GoogleDriveSetupService:
    def __init__(self, auth=None, settings_service=SettingsService):
        self._auth = auth
        self._settings = settings_service
        self._connection = None
        self.account_id = self.account_name = ""
        self._known = {}

    def _authentication(self):
        if self._auth is None:
            self._auth = GoogleDriveAuth()
        return self._auth

    def _clear(self):
        self._connection = None
        self.account_id = self.account_name = ""
        self._known.clear()

    def _folder(self, item_id):
        item = self._connection.service.files().get(fileId=item_id,
            fields="id,name,mimeType,trashed,capabilities(canListChildren)", supportsAllDrives=True).execute()
        if (item.get("trashed") or item.get("mimeType") != "application/vnd.google-apps.folder"
                or item.get("capabilities", {}).get("canListChildren") is not True
                or not isinstance(item.get("id"), str) or not item["id"]
                or not isinstance(item.get("name"), str) or not item["name"]):
            raise GoogleSetupError("Choose an accessible ordinary Google Drive folder.")
        if item_id != "root" and item["id"] != item_id:
            raise GoogleSetupError("The Google folder identity changed. Choose it again.")
        return CloudFolder(item["id"], item["name"])

    def connect(self):
        self._clear()
        try:
            self._connection = self._authentication().connect()
            self.account_id, self.account_name = self._connection.account_id, self._connection.account_name
            folder = self._folder("root")
            self._known[folder.id] = folder
            return folder
        except GoogleOAuthDiagnosticError as error:
            self._clear()
            raise GoogleSetupError(str(error)) from None
        except Exception:
            self._clear()
            raise GoogleSetupError("Google could not connect. Check this build's configuration, consent and connection, then try again.") from None

    def list_folders(self, folder_id):
        if self._connection is None or folder_id not in self._known:
            raise GoogleSetupError("Connect and choose a Google folder first.")
        try:
            self._folder(folder_id)
            folders, seen, page = [], set(), None
            # Values come from Drive but still escape query string literals.
            parent = folder_id.replace("\\", "\\\\").replace("'", "\\'")
            while True:
                result = self._connection.service.files().list(
                    q=f"'{parent}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'",
                    fields="nextPageToken,files(id,name)", pageSize=1000, pageToken=page,
                    supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
                for item in result.get("files", []):
                    if not isinstance(item.get("id"), str) or not item["id"] or not isinstance(item.get("name"), str):
                        raise ValueError()
                    folders.append(CloudFolder(item["id"], item["name"]))
                page = result.get("nextPageToken")
                if not page:
                    break
                if not isinstance(page, str) or page in seen:
                    raise ValueError()
                seen.add(page)
            self._known.update({item.id: item for item in folders})
            return sorted(folders, key=lambda item: (item.name.casefold(), item.id))
        except Exception:
            raise GoogleSetupError("Google folders could not be listed completely. Check access and reconnect.") from None

    def saved_pairs(self):
        return [p for p in self._settings.load().get("folder_pairs", [])
                if p.get("server_endpoint", {}).get("provider") == "google_drive"]

    def _input(self, name, local):
        if not isinstance(name, str) or not name.strip() or not isinstance(local, str) or not local.strip() or not Path(local).is_dir():
            raise GoogleSetupError("Enter a pair name and choose an existing local folder.")

    def save_pair(self, name, local_folder, folder_id):
        self._input(name, local_folder)
        if self._connection is None or folder_id not in self._known:
            raise GoogleSetupError("Connect and choose a Google folder first.")
        try:
            folder = self._folder(folder_id)
        except Exception:
            raise GoogleSetupError("The selected Google folder is no longer accessible.") from None
        settings = self._settings.load()
        pairs = list(settings.get("folder_pairs", []))
        if any(p["name"].casefold() == name.strip().casefold() for p in pairs):
            raise GoogleSetupError("That Folder Pair name is already used.")
        pair = {"name": name.strip(), "local_folder": str(Path(local_folder).resolve()), "server_endpoint": {
            "provider": "google_drive", "account_id": self.account_id, "account_name": self.account_name,
            "folder_id": folder.id, "folder_name": folder.name}}
        self._settings.save(dict(settings, folder_pairs=[*pairs, pair]))
        return pair

    def restore_pair(self, name, *, interactive=False):
        self._clear()
        pair = next((p for p in self.saved_pairs() if p["name"] == name), None)
        if pair is None or not Path(pair["local_folder"]).is_dir():
            raise GoogleSetupError("The saved pair or local folder is unavailable. Edit or reconnect it.")
        endpoint = pair["server_endpoint"]
        try:
            auth = self._authentication()
            self._connection = (auth.connect(expected_account=endpoint["account_id"]) if interactive
                                else auth.acquire_for_account(endpoint["account_id"]))
            if self._connection.account_id != endpoint["account_id"]:
                raise ValueError()
            self.account_id, self.account_name = self._connection.account_id, self._connection.account_name
            folder = self._folder(endpoint["folder_id"])
            self._known[folder.id] = folder
            children = self.list_folders(folder.id)
            current = next((p for p in self.saved_pairs() if p["name"] == name), None)
            if current != pair:
                raise GoogleSetupError("The saved pair changed while opening. Select it again.")
            return pair, folder, children
        except Exception:
            self._clear()
            raise GoogleSetupError("The saved Google account or folder could not be verified. Reconnect that account.") from None

    def prepare_comparison(self, name):
        pair, folder, _ = self.restore_pair(name)
        provider = GoogleDriveProvider(folder.id, folder.name, self.account_name,
            credentials=self._connection.credentials, service=self._connection.service)
        return pair, provider

    def disconnect_pair(self, name):
        pair = next((p for p in self.saved_pairs() if p["name"] == name), None)
        if pair is None:
            raise GoogleSetupError("Choose a saved Google Folder Pair.")
        try:
            self._authentication().forget_account(pair["server_endpoint"]["account_id"])
        except Exception:
            raise GoogleSetupError("The saved Google sign-in could not be removed.") from None
        finally:
            self._clear()

    def _checked_pair(self, expected):
        settings = self._settings.load()
        pairs = list(settings.get("folder_pairs", []))
        index = next((i for i,p in enumerate(pairs) if p["name"] == expected["name"]), None)
        if index is None or pairs[index] != expected or expected["server_endpoint"]["provider"] != "google_drive":
            raise GoogleSetupError("The saved pair changed or was removed. Select it again.")
        return settings, pairs, index

    def edit_pair(self, expected, name, local_folder, folder_id=None):
        self._input(name, local_folder)
        endpoint = dict(expected["server_endpoint"])
        if folder_id is not None:
            if self._connection is None or self.account_id != endpoint["account_id"] or folder_id not in self._known:
                raise GoogleSetupError("Connect the saved Google account before choosing another folder.")
            try:
                folder = self._folder(folder_id)
            except Exception:
                raise GoogleSetupError("The Google folder could not be verified.") from None
            endpoint.update(folder_id=folder.id, folder_name=folder.name)
        settings, pairs, index = self._checked_pair(expected)
        if any(i != index and p["name"].casefold() == name.strip().casefold() for i,p in enumerate(pairs)):
            raise GoogleSetupError("That Folder Pair name is already used.")
        pair = dict(expected, name=name.strip(), local_folder=str(Path(local_folder).resolve()), server_endpoint=endpoint)
        pairs[index] = pair
        self._settings.save(dict(settings, folder_pairs=pairs))
        return pair

    def delete_pair(self, expected):
        settings, pairs, index = self._checked_pair(expected)
        del pairs[index]
        self._settings.save(dict(settings, folder_pairs=pairs))
