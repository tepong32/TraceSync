"""Microsoft Graph OneDrive adapter for TraceSync's storage provider API."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import tempfile

import requests

from core.comparison_evidence import EvidenceMatch, compare_snapshot
from core.storage_provider import (
    ProviderCapability,
    StorageProvider,
    TransferFailed,
    TransferOutcomeUnknown,
    TransferPreconditionFailed,
    TransferPreconditionTarget,
)
from models.backup_content import BackupContent
from models.comparison_metadata import ComparisonMetadata
from models.file_record import FileRecord
from models.storage_location import StorageLocation
from models.sync_history import StorageEndpointSnapshot
from models.transfer_precondition import TransferPrecondition


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"


class OneDriveAmbiguousPathError(ValueError):
    """OneDrive returned names that cannot map uniquely to TraceSync paths."""


class OneDriveProvider(StorageProvider):
    """A selected OneDrive folder with create-only conflict handling.

    Existing files can be read and downloaded. New uploads use Graph upload
    sessions configured to fail on name conflicts; overwrites are unsupported.
    Folder creation is intentionally outside the file-only sync operation.
    """

    def __init__(self, access_token: str, drive_id: str, folder_id: str,
                 folder_name: str, account_name: str, session=None) -> None:
        self.drive_id = drive_id.strip()
        self.folder_id = folder_id.strip()
        self.folder_name = folder_name.strip() or "OneDrive"
        self.account_name = account_name.strip() or "Microsoft account"
        if not all((access_token, self.drive_id, self.folder_id)):
            raise ValueError("A Microsoft account, drive, and folder must be selected.")
        self._access_token = access_token
        self._session = session or requests.Session()
        self._records: dict[str, FileRecord] = {}
        self._parents: dict[str, str] = {"": self.folder_id}
        self._seen_paths: set[str] = set()

    @property
    def display_name(self) -> str:
        return f"OneDrive — {self.account_name}"

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        return frozenset({
            ProviderCapability.TIMESTAMPS,
            ProviderCapability.VERSION_HISTORY,
            ProviderCapability.CONDITIONAL_CREATE,
        })

    def describe_endpoint(self) -> StorageEndpointSnapshot:
        return StorageEndpointSnapshot(
            provider_type="onedrive",
            display_name=f"OneDrive: {self.folder_name}",
            locator=f"{self.drive_id}:folder:{self.folder_id}",
        )

    @classmethod
    def from_token(cls, access_token: str, folder_id: str, folder_name: str, session=None):
        api = session or requests.Session()
        headers = {"Authorization": f"Bearer {access_token}"}
        drive_response = api.get(f"{GRAPH_ROOT}/me/drive", headers=headers, timeout=30)
        _raise_for_response(drive_response, "Could not read the OneDrive drive.")
        profile_response = api.get(f"{GRAPH_ROOT}/me", headers=headers, timeout=30)
        _raise_for_response(profile_response, "Could not read the Microsoft account profile.")
        drive = drive_response.json()
        profile = profile_response.json()
        return cls(access_token, drive["id"], folder_id, folder_name,
                   profile.get("displayName") or profile.get("userPrincipalName"), api)

    def list_folders(self, parent_id: str | None = None) -> list[dict[str, str]]:
        parent_id = parent_id or self.folder_id
        url = f"{GRAPH_ROOT}/drives/{quote(self.drive_id, safe='')}/items/{quote(parent_id, safe='')}/children"
        folders: list[dict[str, str]] = []
        for item in self._paged(url):
            if item.get("folder") is not None:
                folders.append({"id": item["id"], "name": item["name"]})
        return folders

    def scan(self) -> dict[str, FileRecord]:
        self._records.clear()
        self._parents = {"": self.folder_id}
        self._seen_paths.clear()
        self._walk(self.folder_id, "")
        return dict(self._records)

    def _walk(self, parent_id: str, prefix: str) -> None:
        url = f"{GRAPH_ROOT}/drives/{quote(self.drive_id, safe='')}/items/{quote(parent_id, safe='')}/children"
        for item in self._paged(url):
            name = item.get("name", "")
            if not name or name in (".", "..") or "/" in name or "\\" in name:
                raise ValueError("OneDrive contains a name TraceSync cannot safely map to a relative path.")
            relative = f"{prefix}/{name}" if prefix else name
            normalized = relative.casefold()
            if normalized in self._seen_paths:
                raise OneDriveAmbiguousPathError(
                    f"OneDrive has more than one item mapped to '{relative}'. Rename one before comparing."
                )
            self._seen_paths.add(normalized)
            if item.get("folder") is not None:
                self._parents[relative] = item["id"]
                self._walk(item["id"], relative)
            elif item.get("file") is not None:
                record = self._record_from_item(item, relative)
                self._records[relative] = record
            else:
                raise ValueError(
                    f"OneDrive item '{relative}' is a shortcut or unsupported item type."
                )

    def _record_from_item(self, item: dict, relative: str) -> FileRecord:
        modified = item.get("lastModifiedDateTime")
        timestamp = datetime.fromisoformat(modified.replace("Z", "+00:00")).timestamp() if modified else None
        size = int(item.get("size") or 0)
        etag = item.get("eTag") or item.get("cTag")
        location = StorageLocation(
            "onedrive", item["id"], f"OneDrive: {self.folder_name}/{relative}"
        )
        metadata = ComparisonMetadata(
            size=size,
            modified_time=timestamp,
            version_id=etag,
            timestamp_reliable=timestamp is not None,
        )
        return FileRecord.from_location(location, relative, timestamp, size, metadata)

    def get_record(self, relative_path: str) -> FileRecord | None:
        if not self._records:
            self.scan()
        return self._records.get(relative_path)

    def location_for(self, relative_path: str) -> StorageLocation:
        record = self.get_record(relative_path)
        if record is not None:
            return record.storage_location
        parent, separator, name = relative_path.rpartition("/")
        parent_id = self._parents.get(parent) if separator else self.folder_id
        if parent_id is None:
            raise ValueError(
                f"The OneDrive folder '{parent}' does not exist. Create matching folders before syncing."
            )
        return StorageLocation(
            "onedrive", f"{parent_id}/new:{name}",
            f"OneDrive: {self.folder_name}/{relative_path}",
        )

    @contextmanager
    def open_transfer_content(self, relative_path: str, precondition: TransferPrecondition):
        record = self.get_record(relative_path)
        if record is None or not record.storage_location.same_identity_as(precondition.source_location):
            raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE,
                                             "The OneDrive source changed after review.")
        before = self._get_item(record.storage_location.native_id, TransferPreconditionTarget.SOURCE)
        if not _same_version(before, precondition.source_metadata):
            raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE,
                                             "The OneDrive source changed after review.")
        download_url = before.get("@microsoft.graph.downloadUrl")
        if not download_url:
            raise TransferFailed("OneDrive did not provide a download link for this file.")
        with tempfile.NamedTemporaryFile(prefix="tracesync-onedrive-", delete=False) as temporary_file:
            temp_path = Path(temporary_file.name)
        try:
            with self._session.get(download_url, stream=True, timeout=(30, 300)) as response:
                _raise_for_response(response, "The OneDrive file could not be downloaded.")
                with temp_path.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            output.write(chunk)
            after = self._get_item(record.storage_location.native_id, TransferPreconditionTarget.SOURCE)
            if not _same_version(after, precondition.source_metadata):
                raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE,
                                                 "The OneDrive source changed during download.")
            stat = temp_path.stat()
            metadata = precondition.source_metadata
            if metadata.size is not None and stat.st_size != metadata.size:
                raise TransferFailed("The downloaded OneDrive file size did not match its reviewed size.")
            yield BackupContent(temp_path, stat.st_size, stat.st_mtime, metadata)
        finally:
            temp_path.unlink(missing_ok=True)

    def transfer_from(self, source: StorageProvider, relative_path: str,
                      precondition: TransferPrecondition) -> None:
        if not precondition.expects_destination_absent:
            raise TransferFailed("OneDrive overwrite is disabled until remote backup and replacement are supported.")
        if not self.location_for(relative_path).same_identity_as(precondition.destination_location):
            raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                             "The OneDrive destination no longer matches the reviewed folder.")
        self._verify_source(source, relative_path, precondition)
        parent_id = precondition.destination_location.native_id.split("/new:", 1)[0]
        name = relative_path.rsplit("/", 1)[-1]
        parent_path = f"/drives/{quote(self.drive_id, safe='')}/items/{quote(parent_id, safe='')}"
        target_path = f"{parent_path}:/{quote(name, safe='')}:/createUploadSession"
        with source.open_transfer_content(relative_path, precondition) as content:
            if content.size == 0:
                raise TransferFailed("Zero-byte OneDrive upload has not been enabled yet.")
            session_response = self._request(
                "POST", f"{GRAPH_ROOT}{target_path}",
                json={"item": {"name": name, "@microsoft.graph.conflictBehavior": "fail"}},
            )
            upload_url = session_response.get("uploadUrl")
            if not upload_url:
                raise TransferFailed("Microsoft Graph did not return an upload session.")
            try:
                self._upload_session(upload_url, content.local_path, content.size)
            except TransferPreconditionFailed:
                raise
            except TransferFailed:
                raise
            except TransferOutcomeUnknown:
                raise
            except Exception as exc:
                # The upload URL is pre-authorized; never include it in an error.
                raise TransferOutcomeUnknown(
                    "OneDrive upload did not return a reliable completion result. Compare again before retrying."
                ) from exc

    def _upload_session(self, upload_url: str, source_path: Path, size: int) -> None:
        if size == 0:
            raise TransferFailed("Zero-byte OneDrive upload has not been enabled yet.")
        chunk_size = 10 * 1024 * 1024  # multiple of Graph's 320 KiB range unit
        offset = 0
        with source_path.open("rb") as source:
            while offset < size:
                chunk = source.read(min(chunk_size, size - offset))
                end = offset + len(chunk) - 1
                response = self._session.put(
                    upload_url,
                    data=chunk,
                    headers={"Content-Length": str(len(chunk)),
                             "Content-Range": f"bytes {offset}-{end}/{size}"},
                    timeout=(30, 300),
                )
                if response.status_code not in (200, 201, 202):
                    if response.status_code == 409:
                        raise TransferPreconditionFailed(
                            TransferPreconditionTarget.DESTINATION,
                            "A OneDrive file with this name appeared after review.",
                        )
                    if response.status_code == 404:
                        raise TransferFailed(
                            "The OneDrive upload session expired. Compare again before starting a new copy."
                        )
                    if response.status_code >= 500 and offset + len(chunk) == size:
                        raise TransferOutcomeUnknown(
                            "Microsoft Graph did not confirm the final upload response. Compare again before retrying."
                        )
                    _raise_for_response(response, "OneDrive upload failed.")
                if offset + len(chunk) == size and response.status_code not in (200, 201):
                    raise TransferOutcomeUnknown(
                        "OneDrive accepted the final upload bytes but did not confirm the created file. Compare again before retrying."
                    )
                offset += len(chunk)
        # Final range returns the created DriveItem; no token or upload URL is retained.

    def _verify_source(self, source: StorageProvider, relative_path: str,
                       precondition: TransferPrecondition) -> None:
        current = source.get_record(relative_path)
        if (current is None
                or not current.storage_location.same_identity_as(precondition.source_location)
                or compare_snapshot(current.metadata, precondition.source_metadata,
                                    source.capabilities) is not EvidenceMatch.MATCH):
            raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE,
                                             "The source changed after review.")

    def _get_item(self, item_id: str, target=TransferPreconditionTarget.DESTINATION) -> dict:
        url = f"{GRAPH_ROOT}/drives/{quote(self.drive_id, safe='')}/items/{quote(item_id, safe='')}"
        try:
            return self._request("GET", url)
        except TransferPreconditionFailed as error:
            if error.target is TransferPreconditionTarget.DESTINATION:
                raise TransferPreconditionFailed(target, "The OneDrive item is no longer available.") from error
            raise

    def _paged(self, url: str):
        while url:
            if not url.startswith(GRAPH_ROOT + "/"):
                raise TransferFailed("Microsoft Graph returned an unexpected paging URL.")
            response = self._request("GET", url, params={"$top": "200"} if "?" not in url else None)
            yield from response.get("value", [])
            url = response.get("@odata.nextLink")

    def _request(self, method: str, url: str, **kwargs) -> dict:
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("Accept", "application/json")
        try:
            response = self._session.request(method, url, headers=headers, timeout=(30, 120), **kwargs)
        except requests.RequestException as exc:
            raise TransferFailed("Could not reach Microsoft Graph. Check the connection and try again.") from exc
        if response.status_code == 409 and method == "POST" and url.endswith("/createUploadSession"):
            raise TransferPreconditionFailed(
                TransferPreconditionTarget.DESTINATION,
                "A OneDrive file with this name appeared after review.",
            )
        _raise_for_response(response, "Microsoft Graph could not complete the request.")
        if not response.content:
            return {}
        return response.json()


def _same_version(item: dict, expected: ComparisonMetadata) -> bool:
    return (expected.version_id is not None
            and (item.get("eTag") or item.get("cTag")) == expected.version_id)


def _raise_for_response(response, message: str) -> None:
    if response.ok:
        return
    if response.status_code == 404:
        raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                         "The OneDrive item no longer exists.")
    if response.status_code == 412:
        raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                         "The OneDrive item changed after review.")
    raise TransferFailed(f"{message} (HTTP {response.status_code}).")
