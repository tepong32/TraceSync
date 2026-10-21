"""Google Drive v3 storage adapter.

OAuth client configuration is supplied at runtime through environment variables;
no client secrets or refresh tokens are stored in TraceSync settings.
"""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
from pathlib import Path
import tempfile

from core.storage_provider import (
    ConditionalTransferUnsupported,
    ProviderCapability,
    StorageProvider,
    TransferPreconditionFailed,
    TransferPreconditionTarget,
)
from models.backup_content import BackupContent
from models.comparison_metadata import ComparisonMetadata
from models.file_record import FileRecord
from models.storage_location import StorageLocation
from models.sync_history import StorageEndpointSnapshot
from models.transfer_precondition import TransferPrecondition


GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


class GoogleDriveConfigurationError(RuntimeError):
    """Google Drive OAuth or API configuration is missing or invalid."""


class GoogleDriveAmbiguousPathError(ValueError):
    """Drive contains multiple siblings with the same relative path."""


class GoogleDriveUnsupportedItemError(ValueError):
    """Drive contains items that cannot be represented as ordinary files."""


_WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
    *(f"COM{digit}" for digit in "\u00b9\u00b2\u00b3"),
    *(f"LPT{digit}" for digit in "\u00b9\u00b2\u00b3"),
}


def _is_windows_safe_name(name: str) -> bool:
    if (not name or name in {".", ".."} or "/" in name or "\\" in name
            or name[-1] in {".", " "} or any(ord(character) < 32 for character in name)
            or any(character in '<>:"|?*' for character in name)):
        return False
    base_name = name.split(".", 1)[0].rstrip(" .").upper()
    return base_name not in _WINDOWS_RESERVED_NAMES


class GoogleDriveProvider(StorageProvider):
    """A selected Google Drive folder exposed through TraceSync's provider API.

    Drive permits duplicate names. This adapter rejects ambiguous trees and
    cannot be used as a transfer destination because Drive does not provide the
    path-level conditional create required by TraceSync's destination contract.
    """

    def __init__(self, folder_id: str, folder_name: str, account_email: str,
                 credentials=None, service=None) -> None:
        self.folder_id = folder_id.strip()
        self.folder_name = folder_name.strip() or "My Drive"
        self.account_email = account_email.strip()
        if not self.folder_id:
            raise ValueError("A Google Drive folder must be selected.")
        self._credentials = credentials
        self._service = service
        self._records: dict[str, FileRecord] = {}
        self._parents: dict[str, str] = {"": self.folder_id}

    @property
    def display_name(self) -> str:
        return f"Google Drive - {self.account_email}"

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        return frozenset({ProviderCapability.TIMESTAMPS, ProviderCapability.HASHING,
                          ProviderCapability.VERSION_HISTORY})

    def describe_endpoint(self) -> StorageEndpointSnapshot:
        return StorageEndpointSnapshot(
            provider_type="google_drive",
            display_name=f"Google Drive: {self.folder_name}",
            locator=f"{self.account_email}:folder:{self.folder_id}",
        )

    @classmethod
    def authenticate(cls, token_store, client_id: str | None = None):
        """Authenticate through Google Picker and connect one selected folder."""
        from core.google_drive_auth import authenticate_and_pick_folder

        credentials, endpoint = authenticate_and_pick_folder(token_store, client_id)
        return cls.from_credentials(
            endpoint["folder_id"], endpoint["folder_name"], credentials,
        )

    @classmethod
    def from_credentials(cls, folder_id: str, folder_name: str, credentials):
        from googleapiclient.discovery import build
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        about = service.about().get(fields="user(emailAddress)").execute()
        return cls(folder_id, folder_name, about.get("user", {}).get("emailAddress", "Google account"),
                   credentials, service)

    @classmethod
    def from_saved_selection(cls, token_store, endpoint: dict[str, str]):
        """Restore a selected endpoint using only OS-stored OAuth credentials."""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        stored = token_store.get()
        if not stored:
            raise GoogleDriveConfigurationError("Connect to Google Drive again to restore this endpoint.")
        credentials = Credentials.from_authorized_user_info(stored, [GOOGLE_DRIVE_SCOPE])
        if credentials.expired:
            if not credentials.refresh_token:
                raise GoogleDriveConfigurationError("Google Drive sign-in expired. Connect again to continue.")
            credentials.refresh(Request())
            token_store.set(credentials.to_json())
        if not credentials.valid:
            raise GoogleDriveConfigurationError("Google Drive sign-in expired. Connect again to continue.")
        return cls.from_credentials(
            endpoint["folder_id"], endpoint["folder_name"], credentials,
        )

    def list_folders(self, parent_id: str = "root") -> list[dict[str, str]]:
        """List immediate folders for a simple native folder chooser."""
        service = self._api()
        query_parent = self.folder_id if parent_id == "root" else parent_id
        folders: list[dict[str, str]] = []
        page_token = None
        while True:
            response = service.files().list(
                q=f"'{query_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="nextPageToken,files(id,name,mimeType)", pageSize=1000,
                orderBy="name", pageToken=page_token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            folders.extend({"id": item["id"], "name": item["name"]}
                           for item in response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return folders

    def scan(self) -> dict[str, FileRecord]:
        self._records.clear()
        self._parents = {"": self.folder_id}
        self._walk(self.folder_id, "")
        return dict(self._records)

    def _walk(self, folder_id: str, prefix: str) -> None:
        self._assert_folder_can_list_children(folder_id)
        page_token = None
        names_in_folder: dict[str, str] = {}
        while True:
            response = self._api().files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken,files(id,name,mimeType,size,modifiedTime,md5Checksum,version,parents)",
                pageSize=1000, pageToken=page_token,
                supportsAllDrives=True, includeItemsFromAllDrives=True,
            ).execute()
            for item in response.get("files", []):
                name = item.get("name", "")
                if not _is_windows_safe_name(name):
                    raise GoogleDriveUnsupportedItemError(
                        "Google Drive contains a name that Windows cannot safely represent as a file or folder."
                    )
                name_key = name.casefold()
                if name_key in names_in_folder:
                    relative = f"{prefix}/{name}" if prefix else name
                    raise GoogleDriveAmbiguousPathError(
                        f"Google Drive has names that conflict on Windows at '{relative}'. Rename one of them before comparing."
                    )
                names_in_folder[name_key] = name
                relative = f"{prefix}/{name}" if prefix else name
                if relative in self._records:
                    raise GoogleDriveAmbiguousPathError(
                        f"Google Drive has more than one item named '{relative}'. Rename one of them before comparing."
                    )
                if item.get("mimeType") == "application/vnd.google-apps.folder":
                    self._parents[relative] = item["id"]
                    self._walk(item["id"], relative)
                    continue
                if item.get("mimeType", "").startswith("application/vnd.google-apps."):
                    raise GoogleDriveUnsupportedItemError(
                        f"Google Drive item '{relative}' is a Google Workspace document or shortcut; TraceSync cannot safely compare it as a regular file."
                    )
                self._records[relative] = self._to_record(item, relative)
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    def _assert_folder_can_list_children(self, folder_id: str) -> None:
        folder = self._api().files().get(
            fileId=folder_id,
            fields="id,mimeType,trashed,capabilities(canListChildren)",
            supportsAllDrives=True,
        ).execute()
        if (folder.get("trashed") or folder.get("mimeType") != "application/vnd.google-apps.folder"
                or folder.get("capabilities", {}).get("canListChildren") is not True):
            raise GoogleDriveUnsupportedItemError(
                "TraceSync cannot list every item in the selected Google Drive folder tree. "
                "Choose a folder whose contents you can open."
            )

    def _to_record(self, item: dict, relative: str) -> FileRecord:
        location = StorageLocation("google_drive", item["id"],
                                    f"Google Drive: {self.folder_name}/{relative}")
        modified = item.get("modifiedTime")
        from datetime import datetime
        timestamp = datetime.fromisoformat(modified.replace("Z", "+00:00")).timestamp() if modified else None
        size = int(item["size"]) if item.get("size") is not None else None
        metadata = ComparisonMetadata(
            size=size, modified_time=timestamp, content_hash=item.get("md5Checksum"),
            hash_algorithm="md5" if item.get("md5Checksum") else None,
            version_id=str(item["version"]) if item.get("version") else None,
            timestamp_reliable=timestamp is not None,
        )
        return FileRecord.from_location(location=location, relative_path=relative,
                                        modified_time=timestamp, size=size,
                                        comparison_metadata=metadata)

    def get_record(self, relative_path: str) -> FileRecord | None:
        if not self._records:
            self.scan()
        return self._records.get(relative_path)

    def location_for(self, relative_path: str) -> StorageLocation:
        record = self.get_record(relative_path)
        if record:
            return record.storage_location
        parent, _, name = relative_path.rpartition("/")
        parent_id = self._parents.get(parent)
        if not parent_id:
            raise ValueError(f"Google Drive folder is not available: {parent}")
        return StorageLocation("google_drive", f"{parent_id}/new:{name}",
                               f"Google Drive: {self.folder_name}/{relative_path}")

    @contextmanager
    def open_transfer_content(self, relative_path: str, precondition: TransferPrecondition):
        record = self.get_record(relative_path)
        if record is None or not record.storage_location.same_identity_as(precondition.source_location):
            raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The Google Drive source changed after review.")
        latest = self._fetch_record(record.storage_location.native_id, relative_path)
        if (latest is None or not precondition.source_metadata.version_id
                or latest.metadata.version_id != precondition.source_metadata.version_id):
            raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The Google Drive source changed after review.")
        handle = tempfile.NamedTemporaryFile(prefix="tracesync-drive-", delete=False)
        temp_path = Path(handle.name)
        handle.close()
        try:
            request = self._api().files().get_media(fileId=record.storage_location.native_id)
            from googleapiclient.http import MediaIoBaseDownload
            with temp_path.open("wb") as output:
                downloader = MediaIoBaseDownload(output, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            latest = self._fetch_record(record.storage_location.native_id, relative_path)
            if (latest is None or not precondition.source_metadata.version_id
                    or latest.metadata.version_id != precondition.source_metadata.version_id):
                raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The Google Drive source changed during download.")
            downloaded_size = temp_path.stat().st_size
            if latest.metadata.size is not None and downloaded_size != latest.metadata.size:
                raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The Google Drive download did not match the reviewed file size.")
            if latest.metadata.content_hash:
                digest = hashlib.md5()
                with temp_path.open("rb") as downloaded:
                    for chunk in iter(lambda: downloaded.read(1024 * 1024), b""):
                        digest.update(chunk)
                if digest.hexdigest().casefold() != latest.metadata.content_hash.casefold():
                    raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The Google Drive download did not match the provider checksum.")
            yield BackupContent(local_path=temp_path, size=temp_path.stat().st_size,
                                modified_time=latest.modified_time, comparison_metadata=latest.metadata)
        finally:
            temp_path.unlink(missing_ok=True)

    def transfer_from(self, source: StorageProvider, relative_path: str,
                      precondition: TransferPrecondition) -> None:
        raise ConditionalTransferUnsupported(
            "Google Drive uploads are not enabled until the selected folder is configured through Google Picker."
        )

    def _api(self):
        if self._service is None:
            raise GoogleDriveConfigurationError("Sign in to Google Drive before using this location.")
        return self._service

    def _fetch_record(self, item_id: str, relative_path: str) -> FileRecord | None:
        """Fetch fresh metadata instead of trusting the scan cache during transfer."""
        try:
            item = self._api().files().get(
                fileId=item_id,
                fields="id,name,mimeType,size,modifiedTime,md5Checksum,version,parents,trashed",
                supportsAllDrives=True,
            ).execute()
        except Exception as error:
            # Google API errors expose status through the response attribute.
            if getattr(getattr(error, "resp", None), "status", None) == 404:
                return None
            raise
        if item.get("trashed") or item.get("mimeType") == "application/vnd.google-apps.folder":
            return None
        return self._to_record(item, relative_path)
