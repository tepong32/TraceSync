"""Google Drive v3 storage adapter.

OAuth client configuration is supplied at runtime through environment variables;
no client secrets or refresh tokens are stored in TraceSync settings.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import os
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


GOOGLE_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
GOOGLE_CLIENT_ID_ENV = "TRACESYNC_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET_ENV = "TRACESYNC_GOOGLE_CLIENT_SECRET"


class GoogleDriveConfigurationError(RuntimeError):
    """Google Drive OAuth or API configuration is missing or invalid."""


class GoogleDriveAmbiguousPathError(ValueError):
    """Drive contains multiple siblings with the same relative path."""


class GoogleDriveProvider(StorageProvider):
    """A selected Google Drive folder exposed through TraceSync's provider API.

    Drive permits duplicate names. This adapter rejects ambiguous trees and
    checks for a name conflict before creating an item. A conflict created
    concurrently can still result in a duplicate because Drive has no atomic
    path-level create operation; it never replaces an existing Drive item.
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
        return f"Google Drive — {self.account_email}"

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
        """Run installed-app OAuth in a system browser and persist credentials."""
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        client_id = (client_id or os.environ.get(GOOGLE_CLIENT_ID_ENV, "")).strip()
        client_secret = os.environ.get(GOOGLE_CLIENT_SECRET_ENV, "").strip()
        if not client_id:
            raise GoogleDriveConfigurationError(
                f"Set {GOOGLE_CLIENT_ID_ENV} to your Google desktop OAuth client ID."
            )
        if not client_secret:
            raise GoogleDriveConfigurationError(
                f"Set {GOOGLE_CLIENT_SECRET_ENV} to the installed-app OAuth client secret."
            )
        stored = token_store.get()
        credentials = Credentials.from_authorized_user_info(stored, [GOOGLE_DRIVE_SCOPE]) if stored else None
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials or not credentials.valid:
            flow = InstalledAppFlow.from_client_config(
                {"installed": {"client_id": client_id, "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                 "client_secret": client_secret, "token_uri": "https://oauth2.googleapis.com/token",
                 "redirect_uris": ["http://localhost"]}},
                scopes=[GOOGLE_DRIVE_SCOPE],
            )
            credentials = flow.run_local_server(port=0, open_browser=True, access_type="offline", prompt="consent")
        token_store.set(credentials.to_json())
        return credentials

    @classmethod
    def from_credentials(cls, folder_id: str, folder_name: str, credentials):
        from googleapiclient.discovery import build
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        about = service.about().get(fields="user(emailAddress)").execute()
        return cls(folder_id, folder_name, about.get("user", {}).get("emailAddress", "Google account"),
                   credentials, service)

    def list_folders(self, parent_id: str = "root") -> list[dict[str, str]]:
        """List immediate folders for a simple native folder chooser."""
        service = self._api()
        query_parent = self.folder_id if parent_id == "root" else parent_id
        response = service.files().list(
            q=f"'{query_parent}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id,name,mimeType)", pageSize=1000, orderBy="name",
        ).execute()
        return [{"id": item["id"], "name": item["name"]} for item in response.get("files", [])]

    def scan(self) -> dict[str, FileRecord]:
        self._records.clear()
        self._parents = {"": self.folder_id}
        self._walk(self.folder_id, "")
        return dict(self._records)

    def _walk(self, folder_id: str, prefix: str) -> None:
        page_token = None
        while True:
            response = self._api().files().list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="nextPageToken,files(id,name,mimeType,size,modifiedTime,md5Checksum,version,parents)",
                pageSize=1000, pageToken=page_token,
            ).execute()
            for item in response.get("files", []):
                name = item.get("name", "")
                if not name or name in (".", "..") or "/" in name or "\\" in name:
                    raise ValueError("Google Drive contains a name TraceSync cannot safely map to a relative path.")
                relative = f"{prefix}/{name}" if prefix else name
                if relative in self._records:
                    raise GoogleDriveAmbiguousPathError(
                        f"Google Drive has more than one item named '{relative}'. Rename one of them before comparing."
                    )
                if item.get("mimeType") == "application/vnd.google-apps.folder":
                    self._parents[relative] = item["id"]
                    self._walk(item["id"], relative)
                    continue
                self._records[relative] = self._to_record(item, relative)
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    def _to_record(self, item: dict, relative: str) -> FileRecord:
        location = StorageLocation("google_drive", item["id"],
                                    f"Google Drive: {self.folder_name}/{relative}")
        modified = item.get("modifiedTime")
        from datetime import datetime
        timestamp = datetime.fromisoformat(modified.replace("Z", "+00:00")).timestamp() if modified else None
        size = int(item["size"]) if item.get("size") is not None else 0
        metadata = ComparisonMetadata(
            size=size, modified_time=timestamp, content_hash=item.get("md5Checksum"),
            hash_algorithm="md5" if item.get("md5Checksum") else None,
            version_id=str(item["version"]) if item.get("version") else None,
            timestamp_reliable=timestamp is not None,
        )
        return FileRecord.from_location(location=location, relative_path=relative,
                                        modified_time=timestamp or 0.0, size=size,
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
            latest = self.get_record(relative_path)
            if latest is None or not latest.metadata.version_id == precondition.source_metadata.version_id:
                raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The Google Drive source changed during download.")
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
