"""Graph adapter for reviewed files in an already selected personal drive.

Create-only uploads use explicit conflict failure; no replacement or directory
creation fallback is permitted. All HTTP is injectable for offline tests.
"""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import shutil
import tempfile
from urllib.parse import quote, urlsplit

from core.comparison_evidence import EvidenceMatch, compare_snapshot
from core.storage_provider import (StorageProvider, ProviderCapability, TransferFailed,
    TransferPreconditionFailed, TransferPreconditionTarget, TransferOutcomeUnknown,
    ConditionalTransferUnsupported)
from models.backup_content import BackupContent
from models.comparison_metadata import ComparisonMetadata
from models.file_record import FileRecord
from models.storage_location import StorageLocation
from models.sync_history import StorageEndpointSnapshot


GRAPH = "https://graph.microsoft.com/v1.0"


class OneDriveProvider(StorageProvider):
    create_only = True

    def __init__(self, drive_id, folder_id, folder_name, token_supplier, session=None):
        if session is None:
            import requests
            session = requests.Session()
        self.drive_id, self.folder_id, self.folder_name = drive_id, folder_id, folder_name
        self._token_supplier, self._session = token_supplier, session
        self._records = {}
        self._parents = {"": folder_id}
        self._created_parents = {}

    @property
    def display_name(self):
        return "OneDrive: " + self.folder_name

    @property
    def capabilities(self):
        return frozenset({ProviderCapability.TIMESTAMPS, ProviderCapability.VERSION_HISTORY,
                          ProviderCapability.CONDITIONAL_CREATE})

    def describe_endpoint(self):
        return StorageEndpointSnapshot("onedrive", self.display_name, f"{self.drive_id}:folder:{self.folder_id}")

    def _url(self, suffix):
        return f"{GRAPH}/drives/{quote(self.drive_id, safe='')}/{suffix}"

    @staticmethod
    def _path(relative):
        parts = relative.split("/")
        if any(not part or part in (".", "..") or any(c in part for c in '\\:*?"<>|\x00')
               or part.endswith((".", " ")) or any(ord(c) < 32 for c in part) for part in parts):
            raise ValueError("OneDrive contains a path that cannot safely map to a Windows file.")
        # Windows device names remain reserved even when an extension is present.
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                    *(f"LPT{i}" for i in range(1, 10))}
        if any(part.split(".")[0].upper() in reserved for part in parts):
            raise ValueError("OneDrive contains a reserved Windows filename.")
        return parts

    def _request(self, method, url, *, absent_ok=False, **kwargs):
        if not url.startswith(GRAPH + "/"):
            raise TransferFailed("OneDrive returned an unsupported API address.")
        try:
            token = self._token_supplier()  # exact-account renewal, never browser fallback
            response = self._session.request(method, url, headers={"Authorization": f"Bearer {token}"},
                                             timeout=(15, 120), allow_redirects=False, **kwargs)
            if absent_ok and response.status_code == 404:
                return None
            if response.status_code in (409, 412):
                raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                                "The OneDrive destination changed after review.")
            if response.status_code not in (200, 201):
                raise TransferFailed("OneDrive could not complete the request. Check access or reconnect.")
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (TransferFailed, TransferPreconditionFailed):
            raise
        except Exception:
            raise TransferFailed("OneDrive could not complete the request. Reconnect if needed.") from None

    def _item(self, relative):
        self._path(relative)
        return self._request("GET", self._url(f"items/{quote(self.folder_id, safe='')}:/{quote(relative, safe='/')}"), absent_ok=True)

    def _record(self, item, relative):
        if "file" not in item or "remoteItem" in item or "deleted" in item:
            raise TransferFailed("The OneDrive path is not an ordinary file.")
        if item.get("name") != relative.rsplit("/", 1)[-1]:
            raise TransferFailed("OneDrive returned a different filename.")
        modified = item.get("lastModifiedDateTime")
        timestamp = datetime.fromisoformat(modified.replace("Z", "+00:00")).timestamp() if modified else None
        metadata = ComparisonMetadata(size=int(item["size"]), modified_time=timestamp,
                                      version_id=item.get("eTag"), timestamp_reliable=timestamp is not None)
        location = StorageLocation("onedrive", f"{self.drive_id}/item:{item['id']}", f"{self.display_name}/{relative}")
        return FileRecord.from_location(location, relative, timestamp, metadata.size, metadata)

    def scan(self):
        self._records, self._parents = {}, {"": self.folder_id}
        self._created_parents = {}
        seen_paths, seen_folders = set(), set()
        def walk(parent, prefix):
            if parent in seen_folders:
                raise TransferFailed("OneDrive returned a repeated folder.")
            seen_folders.add(parent)
            url = self._url(f"items/{quote(parent, safe='')}/children")
            pages = set()
            while url:
                if url in pages:
                    raise TransferFailed("OneDrive repeated a listing page.")
                pages.add(url)
                page = self._request("GET", url)
                for item in page.get("value", []):
                    if "/" in item["name"]:
                        raise TransferFailed("OneDrive returned an invalid item name.")
                    relative = prefix + item["name"]
                    self._path(relative)
                    if relative.casefold() in seen_paths or "remoteItem" in item or "deleted" in item:
                        raise TransferFailed("OneDrive contains ambiguous names or unsupported shortcuts.")
                    seen_paths.add(relative.casefold())
                    if "folder" in item:
                        self._parents[relative] = item["id"]
                        walk(item["id"], relative + "/")
                    else:
                        self._records[relative] = self._record(item, relative)
                url = page.get("@odata.nextLink")
        try:
            walk(self.folder_id, "")
        except Exception:
            self._records, self._parents = {}, {"": self.folder_id}
            raise
        return dict(self._records)

    def get_record(self, relative_path):
        item = self._item(relative_path)
        return self._record(item, relative_path) if item is not None else None

    def location_for(self, relative_path):
        self._path(relative_path)
        if relative_path in self._records:
            return self._records[relative_path].storage_location
        parent, _, name = relative_path.rpartition("/")
        if parent not in self._parents:
            return StorageLocation("onedrive", f"{self.drive_id}/pending:{self.folder_id}/{relative_path}",
                                   f"{self.display_name}/{relative_path}")
        return StorageLocation("onedrive", f"{self.drive_id}/parent:{self._parents[parent]}/new:{name}",
                               f"{self.display_name}/{relative_path}")

    @staticmethod
    def _signed_url(url):
        parsed = urlsplit(url or "")
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise TransferFailed("OneDrive returned an invalid transfer address.")
        return url

    def _reviewed_source(self, relative, precondition):
        item = self._item(relative)
        record = self._record(item, relative) if item else None
        if (record is None or not record.storage_location.same_identity_as(precondition.source_location)
                or not precondition.source_metadata.version_id
                or record.metadata != precondition.source_metadata):
            raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The OneDrive source changed after review.")
        return item

    @contextmanager
    def open_transfer_content(self, relative_path, precondition):
        item = self._reviewed_source(relative_path, precondition)
        url = self._signed_url(item.get("@microsoft.graph.downloadUrl"))
        with tempfile.TemporaryDirectory(prefix="tracesync-onedrive-") as directory:
            path = Path(directory) / "content"
            try:
                with self._session.get(url, stream=True, timeout=(15, 120), allow_redirects=False) as response:
                    if response.status_code != 200:
                        raise TransferFailed("OneDrive download failed.")
                    with path.open("wb") as output:
                        for chunk in response.iter_content(1024 * 1024):
                            output.write(chunk)
            except Exception:
                raise TransferFailed("OneDrive download failed.") from None
            self._reviewed_source(relative_path, precondition)
            if path.stat().st_size != precondition.source_metadata.size:
                raise TransferFailed("OneDrive download did not match the reviewed size.")
            yield BackupContent(path, path.stat().st_size, precondition.source_metadata.modified_time,
                                precondition.source_metadata)

    def transfer_from(self, source, relative_path, precondition):
        if not precondition.expects_destination_absent:
            raise ConditionalTransferUnsupported("OneDrive overwrites are disabled.")
        location = self.location_for(relative_path)
        if not location.same_identity_as(precondition.destination_location) or not any(marker in location.native_id for marker in ("/new:", "/pending:")):
            raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION, "The reviewed destination changed.")
        if self._item(relative_path) is not None:
            raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION, "The destination appeared after review.")
        parent, _, name = relative_path.rpartition("/")
        with source.open_transfer_content(relative_path, precondition) as content, tempfile.TemporaryDirectory(prefix="tracesync-upload-") as directory:
            snapshot = Path(directory) / "content"
            shutil.copyfile(content.local_path, snapshot)
            current = source.get_record(relative_path)
            if (current is None or not current.storage_location.same_identity_as(precondition.source_location)
                    or compare_snapshot(current.metadata, precondition.source_metadata, source.capabilities) is not EvidenceMatch.MATCH
                    or snapshot.stat().st_size != precondition.source_metadata.size):
                raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The source changed while preparing upload.")
            size = snapshot.stat().st_size
            parent_id = self._ensure_parent(parent)
            if size == 0:
                self._create_empty(parent_id, name)
                return
            session = self._request("POST", self._url(f"items/{quote(parent_id, safe='')}:/{quote(name, safe='')}:/createUploadSession"),
                                    json={"item": {"name": name, "@microsoft.graph.conflictBehavior": "fail"}})
            self._upload(self._signed_url(session.get("uploadUrl")), snapshot, size, name, parent_id)

    def required_directories(self, relative_path):
        parts = self._path(relative_path)[:-1]
        return tuple("/".join(parts[:i]) for i in range(1, len(parts) + 1)
                     if "/".join(parts[:i]) not in self._parents)

    def _ensure_parent(self, parent):
        parent_id = self.folder_id
        parts = parent.split("/") if parent else []
        for index, name in enumerate(parts):
            path = "/".join(parts[:index + 1])
            expected = self._parents.get(path) or self._created_parents.get(path)
            current = self._item(path)
            if expected:
                if (not current or current.get("id") != expected or "folder" not in current
                        or "remoteItem" in current or "deleted" in current):
                    raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                                    "The destination folder changed.")
                parent_id = expected
            else:
                if current is not None:
                    raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                                    "A destination folder appeared after review.")
                data = self._create_request("POST", self._url(f"items/{quote(parent_id, safe='')}/children"),
                    json={"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"})
                self._verify_created(data, name, parent_id, folder=True)
                parent_id = data["id"]
                self._created_parents[path] = parent_id
        return parent_id

    def _create_request(self, method, url, **kwargs):
        # A timeout or malformed reply after a mutating request is ambiguous.
        try:
            response = self._session.request(method, url,
                headers={"Authorization": f"Bearer {self._token_supplier()}", "Content-Type": "application/json" if "json" in kwargs else "application/octet-stream"},
                timeout=(15, 120), allow_redirects=False, **kwargs)
            if response.status_code in (409, 412):
                raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                                "The destination appeared during creation.")
            if response.status_code != 201:
                raise TransferOutcomeUnknown("Creation was not confirmed. Compare again before retrying.")
            return response.json()
        except (TransferPreconditionFailed, TransferOutcomeUnknown):
            raise
        except Exception:
            raise TransferOutcomeUnknown("Creation outcome is unknown. Compare again before retrying.") from None

    @staticmethod
    def _verify_created(data, name, parent_id, *, folder=False):
        if (not isinstance(data, dict) or not data.get("id") or data.get("name") != name
                or ("folder" if folder else "file") not in data
                or "remoteItem" in data or "deleted" in data
                or data.get("parentReference", {}).get("id") != parent_id
                or (not folder and data.get("size") != 0)):
            raise TransferOutcomeUnknown("Created item did not match the reviewed destination. Compare again.")

    def _create_empty(self, parent_id, name):
        url = self._url(f"items/{quote(parent_id, safe='')}:/{quote(name, safe='')}:/content")
        data = self._create_request("PUT", url + "?@microsoft.graph.conflictBehavior=fail", data=b"")
        self._verify_created(data, name, parent_id)

    def _upload(self, url, path, size, name, parent_id):
        offset, chunk_size = 0, 10 * 1024 * 1024
        with path.open("rb") as source:
            while offset < size:
                chunk = source.read(min(chunk_size, size - offset))
                if not chunk:
                    raise TransferFailed("The staged upload became unavailable.")
                final = offset + len(chunk) == size
                try:
                    response = self._session.put(url, data=chunk, timeout=(15, 120), allow_redirects=False,
                        headers={"Content-Length": str(len(chunk)), "Content-Range": f"bytes {offset}-{offset+len(chunk)-1}/{size}"})
                    if response.status_code in (409, 412):
                        raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION, "The destination appeared during upload.")
                    data = response.json()
                    if final:
                        if (response.status_code not in (200, 201) or not data.get("id") or data.get("name") != name
                                or data.get("size") != size or "file" not in data
                                or data.get("parentReference", {}).get("id") != parent_id):
                            raise TransferOutcomeUnknown("OneDrive did not confirm the reviewed file. Compare again before retrying.")
                    elif response.status_code != 202 or data.get("nextExpectedRanges") != [f"{offset+len(chunk)}-"]:
                        raise TransferOutcomeUnknown("OneDrive upload progress is uncertain. Compare again before retrying.")
                except (TransferPreconditionFailed, TransferOutcomeUnknown):
                    raise
                except Exception:
                    raise TransferOutcomeUnknown("OneDrive upload outcome is unknown. Compare again before retrying.") from None
                offset += len(chunk)
