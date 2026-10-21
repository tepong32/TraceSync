"""Graph adapter for reviewed files in an already selected personal drive.

Create-only uploads use explicit conflict failure; no replacement or directory
creation fallback is permitted. All HTTP is injectable for offline tests.
"""
import os
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
from urllib.parse import quote, urlsplit

from core.comparison_evidence import EvidenceMatch, compare_snapshot
from core.onedrive_timestamps import parse_modified_time, format_modified_time
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
        self._notes = {}
        self._uncertain_parents = set()

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
        reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                    *(f"COM{digit}" for digit in "¹²³"), *(f"LPT{digit}" for digit in "¹²³"),
                    *(f"COM{i}" for i in range(1, 10)),
                    *(f"LPT{i}" for i in range(1, 10))}
        if any(part.split(".")[0].rstrip(" .").upper() in reserved for part in parts):
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
        client_info = item.get("fileSystemInfo")
        modified = (client_info.get("lastModifiedDateTime") if isinstance(client_info, dict) else None)
        modified = modified or item.get("lastModifiedDateTime")
        timestamp = parse_modified_time(modified) if modified else None
        metadata = ComparisonMetadata(size=int(item["size"]), modified_time=timestamp,
                                      version_id=item.get("eTag"), timestamp_reliable=timestamp is not None)
        location = StorageLocation("onedrive", f"{self.drive_id}/item:{item['id']}", f"{self.display_name}/{relative}")
        return FileRecord.from_location(location, relative, timestamp, metadata.size, metadata)

    def scan(self):
        self._records, self._parents = {}, {"": self.folder_id}
        self._created_parents = {}
        self._uncertain_parents.clear()
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

    def _reviewed_source(self, relative, source_location, source_metadata):
        item = self._item(relative)
        record = self._record(item, relative) if item else None
        if (record is None or not record.storage_location.same_identity_as(source_location)
                or not source_metadata.version_id
                or record.metadata != source_metadata):
            raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The OneDrive source changed after review.")
        return item

    @contextmanager
    def open_transfer_content(self, relative_path, precondition):
        with self._materialize_reviewed_content(relative_path, precondition.source_location,
                                                precondition.source_metadata) as content:
            yield content

    @contextmanager
    def open_backup_content(self, relative_path):
        record = self.get_record(relative_path)
        if record is None:
            raise TransferFailed("The OneDrive file is unavailable for a verified backup.")
        with self._materialize_reviewed_content(relative_path, record.storage_location, record.metadata) as content:
            yield content

    @contextmanager
    def _materialize_reviewed_content(self, relative_path, source_location, source_metadata):
        item = self._reviewed_source(relative_path, source_location, source_metadata)
        url = self._signed_url(item.get("@microsoft.graph.downloadUrl"))
        with tempfile.TemporaryDirectory(prefix="tracesync-onedrive-", ignore_cleanup_errors=True) as directory:
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
            self._reviewed_source(relative_path, source_location, source_metadata)
            if path.stat().st_size != source_metadata.size:
                raise TransferFailed("OneDrive download did not match the reviewed size.")
            if source_metadata.modified_time is not None:
                os.utime(path, (source_metadata.modified_time, source_metadata.modified_time))
            materialized = path.stat()
            yield BackupContent(path, materialized.st_size, materialized.st_mtime, source_metadata)

    def transfer_from(self, source, relative_path, precondition):
        self._notes[relative_path] = []
        if precondition.destination_folders != self.folder_plan(relative_path):
            raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                            "The reviewed folder plan changed. Compare again.")
        if not precondition.expects_destination_absent:
            raise ConditionalTransferUnsupported("OneDrive overwrites are disabled.")
        location = self.location_for(relative_path)
        if not location.same_identity_as(precondition.destination_location) or not any(marker in location.native_id for marker in ("/new:", "/pending:")):
            raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION, "The reviewed destination changed.")
        if self._item(relative_path) is not None:
            raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION, "The destination appeared after review.")
        parent, _, name = relative_path.rpartition("/")
        with source.open_transfer_content(relative_path, precondition) as content, tempfile.TemporaryDirectory(prefix="tracesync-upload-", ignore_cleanup_errors=True) as directory:
            snapshot = Path(directory) / "content"
            shutil.copyfile(content.local_path, snapshot)
            current = source.get_record(relative_path)
            if (current is None or not current.storage_location.same_identity_as(precondition.source_location)
                    or compare_snapshot(current.metadata, precondition.source_metadata, source.capabilities) is not EvidenceMatch.MATCH
                    or snapshot.stat().st_size != precondition.source_metadata.size):
                raise TransferPreconditionFailed(TransferPreconditionTarget.SOURCE, "The source changed while preparing upload.")
            size = snapshot.stat().st_size
            modified = precondition.source_metadata.modified_time
            stamp = format_modified_time(modified) if modified is not None else None
            parent_id = self._ensure_parent(parent, relative_path)
            # Recheck the full chain after creation, before publishing file content.
            self._ensure_parent(parent, relative_path)
            if size == 0:
                created = self._create_empty(parent_id, name)
            else:
                properties = {"name": name, "@microsoft.graph.conflictBehavior": "fail"}
                if stamp is not None:
                    properties["fileSystemInfo"] = {"lastModifiedDateTime": stamp}
                session = self._request("POST", self._url(f"items/{quote(parent_id, safe='')}:/{quote(name, safe='')}:/createUploadSession"),
                                        json={"item": properties})
                created = self._upload(self._signed_url(session.get("uploadUrl")), snapshot, size, name, parent_id)
            if stamp is not None:
                self._preserve_client_time(created, name, parent_id, size, stamp, relative_path)

    def begin_transfer_run(self):
        self._created_parents = {}
        self._notes = {}

    def folder_plan(self, relative_path):
        parts = self._path(relative_path)[:-1]
        return (("", self.folder_id),) + tuple(
            ("/".join(parts[:i]), self._parents.get("/".join(parts[:i])))
            for i in range(1, len(parts) + 1))

    def transfer_notes(self, relative_path):
        return " ".join(self._notes.pop(relative_path, ()))

    def _ensure_parent(self, parent, relative_path):
        root = self._request("GET", self._url(f"items/{quote(self.folder_id, safe='')}"))
        if (root.get("id") != self.folder_id or "folder" not in root
                or "remoteItem" in root or "deleted" in root):
            raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION, "The selected destination changed.")
        parent_id = self.folder_id
        parts = parent.split("/") if parent else []
        for index, name in enumerate(parts):
            path = "/".join(parts[:index + 1])
            expected = self._parents.get(path) or self._created_parents.get(path)
            if path in self._uncertain_parents:
                raise TransferOutcomeUnknown("A prior folder creation is uncertain. Compare again before retrying.")
            current = self._item(path)
            if expected:
                if (not current or current.get("id") != expected or "folder" not in current
                        or "remoteItem" in current or "deleted" in current
                        or current.get("parentReference", {}).get("id") != parent_id):
                    raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                                    "The destination folder changed.")
                parent_id = expected
            else:
                if current is not None:
                    raise TransferPreconditionFailed(TransferPreconditionTarget.DESTINATION,
                                                    "A destination folder appeared after review.")
                try:
                    data = self._create_request("POST", self._url(f"items/{quote(parent_id, safe='')}/children"),
                        json={"name": name, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"})
                    self._verify_created(data, name, parent_id, folder=True)
                except TransferOutcomeUnknown:
                    self._uncertain_parents.add(path)
                    self._notes[relative_path].append(f"Folder creation uncertain: {path}. Compare again; no cleanup attempted.")
                    raise
                self._notes[relative_path].append(f"Created cloud folder: {path}. No automatic cleanup is attempted.")
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
            if response.status_code in (400, 401, 403, 404, 405, 413, 415, 429):
                raise TransferFailed("OneDrive rejected creation. Check access and compare again.")
            if response.status_code != 201:
                raise TransferOutcomeUnknown("Creation was not confirmed. Compare again before retrying.")
            return response.json()
        except (TransferPreconditionFailed, TransferOutcomeUnknown, TransferFailed):
            raise
        except Exception:
            raise TransferOutcomeUnknown("Creation outcome is unknown. Compare again before retrying.") from None

    def _verify_created(self, data, name, parent_id, *, folder=False, size=0):
        parent = data.get("parentReference") if isinstance(data, dict) else None
        facet = "folder" if folder else "file"
        if (not isinstance(data, dict) or not isinstance(data.get("id"), str) or not data["id"]
                or data.get("name") != name or not isinstance(data.get(facet), dict)
                or ("file" if folder else "folder") in data
                or "remoteItem" in data or "deleted" in data
                or not isinstance(parent, dict) or parent.get("id") != parent_id
                or parent.get("driveId", self.drive_id) != self.drive_id
                or (not folder and (type(data.get("size")) is not int or data["size"] != size))):
            raise TransferOutcomeUnknown("Created item did not match the reviewed destination. Compare again.")

    def _create_empty(self, parent_id, name):
        url = self._url(f"items/{quote(parent_id, safe='')}:/{quote(name, safe='')}:/content")
        data = self._create_request("PUT", url + "?@microsoft.graph.conflictBehavior=fail", data=b"")
        self._verify_created(data, name, parent_id)
        return data

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
                    if response.status_code in (400, 401, 403, 404, 405, 413, 415, 429):
                        raise TransferFailed("OneDrive rejected the upload. Check access and compare again.")
                    data = response.json()
                    if final:
                        if response.status_code not in (200, 201):
                            raise TransferOutcomeUnknown("OneDrive did not confirm the reviewed file. Compare again before retrying.")
                        self._verify_created(data, name, parent_id, size=size)
                        return data
                    elif response.status_code != 202 or data.get("nextExpectedRanges") != [f"{offset+len(chunk)}-"]:
                        raise TransferOutcomeUnknown("OneDrive upload progress is uncertain. Compare again before retrying.")
                except (TransferPreconditionFailed, TransferOutcomeUnknown, TransferFailed):
                    raise
                except Exception:
                    raise TransferOutcomeUnknown("OneDrive upload outcome is unknown. Compare again before retrying.") from None
                offset += len(chunk)

    def _preserve_client_time(self, created, name, parent_id, size, stamp, relative_path):
        """Metadata only, bound to confirmed new ID/version; never retry."""
        warning = "File copied; preserving its modification time was not confirmed. Compare again. No retry attempted."
        try:
            info = created.get("fileSystemInfo")
            if isinstance(info, dict) and parse_modified_time(info.get("lastModifiedDateTime", "")) == parse_modified_time(stamp):
                return
        except (ValueError, TypeError, AttributeError):
            pass
        version = created.get("eTag")
        if not isinstance(version, str) or not version.strip():
            self._notes[relative_path].append(warning)
            return
        try:
            response = self._session.request("PATCH", self._url(f"items/{quote(created['id'], safe='')}"),
                headers={"Authorization": f"Bearer {self._token_supplier()}", "Content-Type": "application/json", "If-Match": version},
                json={"fileSystemInfo": {"lastModifiedDateTime": stamp}},
                timeout=(15, 120), allow_redirects=False)
            if response.status_code != 200:
                self._notes[relative_path].append(warning)
                return
            updated = response.json()
            self._verify_created(updated, name, parent_id, size=size)
            if (updated["id"] != created["id"]
                    or parse_modified_time(updated["fileSystemInfo"]["lastModifiedDateTime"]) != parse_modified_time(stamp)):
                raise ValueError()
        except Exception:
            # Content creation was already positively confirmed. A metadata-only
            # error must not relabel known copied bytes as failed or unknown.
            self._notes[relative_path].append(warning)
