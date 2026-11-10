"""SFTP storage provider with strict host verification and create-only writes."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import errno
import json
import posixpath
import stat
import tempfile
from pathlib import Path
from typing import Iterator

from core.comparison_evidence import EvidenceMatch, compare_snapshot
from core.storage_provider import (
    ConditionalTransferUnsupported,
    ProviderCapability,
    StorageProvider,
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


@dataclass(frozen=True, slots=True)
class SftpEndpoint:
    """Non-secret SFTP connection settings.

    Passwords are retrieved from the OS keyring at connection time using
    ``credential_key``. Neither passwords nor private-key contents belong in
    this object or in application settings.
    """

    host: str
    username: str
    remote_root: str
    port: int = 22
    credential_key: str | None = None
    private_key_file: str | None = None
    known_hosts_file: str | None = None
    timeout_seconds: float = 15.0

    def __post_init__(self) -> None:
        if not self.host.strip() or not self.username.strip():
            raise ValueError("SFTP host and username are required.")
        if any(character in self.host for character in "/\\@?#") or any(
            character.isspace() for character in self.host
        ):
            raise ValueError("Enter an SFTP host name or IP address without a URL or path.")
        if not 1 <= self.port <= 65535:
            raise ValueError("SFTP port must be between 1 and 65535.")
        if self.timeout_seconds <= 0:
            raise ValueError("SFTP timeout must be positive.")
        if not self.remote_root.strip():
            raise ValueError("An explicit SFTP folder path is required.")
        root = posixpath.normpath("/" + self.remote_root.lstrip("/"))
        object.__setattr__(self, "remote_root", root)


class SftpStorageProvider(StorageProvider):
    """Remote folder provider that refuses unknown host keys and overwrites."""

    def __init__(self, endpoint: SftpEndpoint) -> None:
        self.endpoint = endpoint

    @property
    def display_name(self) -> str:
        return "SFTP"

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        # SFTP modification times are server-provided. Existing remote files
        # are deliberately never replaced.
        return frozenset({
            ProviderCapability.TIMESTAMPS,
            ProviderCapability.CONDITIONAL_CREATE,
        })

    def describe_endpoint(self) -> StorageEndpointSnapshot:
        return StorageEndpointSnapshot(
            provider_type="sftp",
            display_name=self.display_name,
            locator=f"sftp://{self.endpoint.host}:{self.endpoint.port}{self.endpoint.remote_root}",
        )

    def location_for(self, relative_path: str) -> StorageLocation:
        safe_relative = _normalize_relative_path(relative_path)
        remote_path = posixpath.normpath(
            posixpath.join(self.endpoint.remote_root, safe_relative)
        )
        if remote_path != self.endpoint.remote_root and not remote_path.startswith(
            self.endpoint.remote_root.rstrip("/") + "/"
        ):
            raise ValueError("The file path is outside the selected SFTP folder.")
        identity = json.dumps(
            [
                self.endpoint.host.casefold(),
                self.endpoint.port,
                self.endpoint.username,
                remote_path,
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        display = f"{self.endpoint.host}:{self.endpoint.port}:{remote_path}"
        return StorageLocation("sftp", identity, display)

    def scan(self) -> dict[str, FileRecord]:
        records: dict[str, FileRecord] = {}
        with self._sftp_client() as sftp:
            self._require_directory(sftp, self.endpoint.remote_root)
            self._scan_directory(sftp, self.endpoint.remote_root, "", records)
        return records

    def get_record(self, relative_path: str) -> FileRecord | None:
        location = self.location_for(relative_path)
        with self._sftp_client() as sftp:
            try:
                attrs = sftp.lstat(self._remote_path(relative_path))
            except OSError as exc:
                if getattr(exc, "errno", None) == errno.ENOENT:
                    return None
                raise
        if attrs.st_mode is None or not stat.S_ISREG(attrs.st_mode):
            return None
        metadata = _metadata_from_attrs(attrs)
        return FileRecord.from_location(
            location=location,
            relative_path=_normalize_relative_path(relative_path),
            modified_time=metadata.modified_time,
            size=attrs.st_size,
            comparison_metadata=metadata,
        )

    def transfer_from(
        self,
        source: StorageProvider,
        relative_path: str,
        precondition: TransferPrecondition,
    ) -> None:
        self._verify_source(source, relative_path, precondition)
        destination = self.location_for(relative_path)
        if not destination.same_identity_as(precondition.destination_location):
            raise TransferPreconditionFailed(
                TransferPreconditionTarget.DESTINATION,
                "The transfer destination does not match the reviewed location.",
            )
        if not precondition.expects_destination_absent:
            raise ConditionalTransferUnsupported(
                "SFTP synchronization supports new files only; remote replacement is disabled."
            )

        remote_path = self._remote_path(relative_path)
        with source.open_transfer_content(relative_path, precondition) as content:
            self._verify_source(source, relative_path, precondition)
            with self._sftp_client() as sftp:
                self._ensure_parent_directories(sftp, posixpath.dirname(remote_path))
                self._reject_symlink_parents(sftp, posixpath.dirname(remote_path))
                try:
                    remote_file = sftp.open(remote_path, "x")
                except OSError as exc:
                    if self._is_already_exists(exc) or self._remote_item_exists(
                        sftp,
                        remote_path,
                    ):
                        raise TransferPreconditionFailed(
                            TransferPreconditionTarget.DESTINATION,
                            "A destination file appeared after the transfer was reviewed.",
                        ) from exc
                    raise

                # Once exclusive create succeeds, a connection loss can leave a
                # partial remote file. Never retry or delete an uncertain result.
                try:
                    with content.local_path.open("rb") as source_file:
                        while chunk := source_file.read(1024 * 1024):
                            remote_file.write(chunk)
                    self._verify_source(source, relative_path, precondition)
                    remote_file.flush()
                    remote_file.close()
                except Exception as exc:
                    try:
                        remote_file.close()
                    except Exception:
                        pass
                    raise TransferOutcomeUnknown(
                        "The SFTP upload started but its final remote state is unknown. "
                        "Compare the folders again before retrying."
                    ) from exc

    @contextmanager
    def open_transfer_content(
        self,
        relative_path: str,
        precondition: TransferPrecondition,
    ) -> Iterator[BackupContent]:
        self._verify_source(self, relative_path, precondition)
        expected_location = self.location_for(relative_path)
        if not expected_location.same_identity_as(precondition.source_location):
            raise TransferPreconditionFailed(
                TransferPreconditionTarget.SOURCE,
                "The transfer source does not match the reviewed location.",
            )

        remote_path = self._remote_path(relative_path)
        with tempfile.TemporaryDirectory(prefix="tracesync-sftp-") as temp_directory:
            local_path = Path(temp_directory) / Path(relative_path).name
            with self._sftp_client() as sftp:
                with sftp.open(remote_path, "rb") as remote_file:
                    with local_path.open("wb") as local_file:
                        while chunk := remote_file.read(1024 * 1024):
                            local_file.write(chunk)
                        local_file.flush()
            local_stat = local_path.stat()
            expected_size = precondition.source_metadata.size
            if expected_size is not None and local_stat.st_size != expected_size:
                raise TransferPreconditionFailed(
                    TransferPreconditionTarget.SOURCE,
                    "The SFTP source changed while it was being downloaded.",
                )
            self._verify_source(self, relative_path, precondition)
            yield BackupContent(
                local_path=local_path,
                size=local_stat.st_size,
                modified_time=local_stat.st_mtime,
                comparison_metadata=precondition.source_metadata,
            )

    @contextmanager
    def _sftp_client(self) -> Iterator[object]:
        try:
            import paramiko
        except ImportError as exc:
            raise RuntimeError(
                "SFTP support requires the Paramiko package."
            ) from exc

        client = paramiko.SSHClient()
        if self.endpoint.known_hosts_file:
            known_hosts = Path(self.endpoint.known_hosts_file)
            if not known_hosts.is_file():
                raise RuntimeError("The configured SFTP known-hosts file does not exist.")
            client.load_host_keys(str(known_hosts))
        else:
            client.load_system_host_keys()
        # RejectPolicy is Paramiko's default; state it explicitly so unknown
        # hosts can never be trusted implicitly by this provider.
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

        connect_options: dict[str, object] = {
            "hostname": self.endpoint.host,
            "port": self.endpoint.port,
            "username": self.endpoint.username,
            "timeout": self.endpoint.timeout_seconds,
            "banner_timeout": self.endpoint.timeout_seconds,
            "auth_timeout": self.endpoint.timeout_seconds,
            "allow_agent": True,
            "look_for_keys": True,
        }
        if self.endpoint.private_key_file:
            connect_options["key_filename"] = self.endpoint.private_key_file
        if self.endpoint.credential_key:
            try:
                import keyring
            except ImportError as exc:
                raise RuntimeError(
                    "SFTP password retrieval requires the keyring package."
                ) from exc
            password = keyring.get_password("TraceSync SFTP", self.endpoint.credential_key)
            if password is None:
                raise RuntimeError("No saved password is available for this SFTP profile.")
            connect_options["password"] = password

        try:
            client.connect(**connect_options)
            sftp = client.open_sftp()
            try:
                yield sftp
            finally:
                sftp.close()
        finally:
            client.close()

    def _scan_directory(
        self,
        sftp: object,
        remote_directory: str,
        relative_directory: str,
        records: dict[str, FileRecord],
    ) -> None:
        for attrs in sftp.listdir_attr(remote_directory):
            if attrs.filename in {".", ".."} or attrs.st_mode is None:
                continue
            remote_path = posixpath.join(remote_directory, attrs.filename)
            relative_path = posixpath.join(relative_directory, attrs.filename)
            mode = attrs.st_mode
            if stat.S_ISDIR(mode):
                self._scan_directory(sftp, remote_path, relative_path, records)
            elif stat.S_ISREG(mode):
                location = self.location_for(relative_path)
                metadata = _metadata_from_attrs(attrs)
                records[relative_path] = FileRecord.from_location(
                    location=location,
                    relative_path=relative_path,
                    modified_time=metadata.modified_time,
                    size=attrs.st_size,
                    comparison_metadata=metadata,
                )
            # Symbolic links and special files are excluded from the sync view.

    def _remote_path(self, relative_path: str) -> str:
        return posixpath.join(
            self.endpoint.remote_root,
            _normalize_relative_path(relative_path),
        )

    @staticmethod
    def _require_directory(sftp: object, path: str) -> None:
        attrs = sftp.lstat(path)
        if not stat.S_ISDIR(attrs.st_mode):
            raise NotADirectoryError("The configured SFTP root is not a directory.")

    def _ensure_parent_directories(self, sftp: object, directory: str) -> None:
        root = self.endpoint.remote_root
        self._reject_symlink_parents(sftp, directory)
        current = root
        suffix = directory[len(root):].strip("/")
        for component in filter(None, suffix.split("/")):
            current = posixpath.join(current, component)
            try:
                attrs = sftp.lstat(current)
            except OSError:
                sftp.mkdir(current)
                attrs = sftp.lstat(current)
            if not stat.S_ISDIR(attrs.st_mode):
                raise NotADirectoryError("An SFTP destination parent is not a directory.")

    def _reject_symlink_parents(self, sftp: object, directory: str) -> None:
        root = self.endpoint.remote_root
        self._require_directory(sftp, root)
        if root == "/":
            current = "/"
            suffix = directory.lstrip("/")
        else:
            if directory != root and not directory.startswith(root.rstrip("/") + "/"):
                raise ValueError("The file path is outside the selected SFTP folder.")
            current = root
            suffix = directory[len(root):].strip("/")
        for component in filter(None, suffix.split("/")):
            current = posixpath.join(current, component)
            try:
                attrs = sftp.lstat(current)
            except OSError:
                continue
            if stat.S_ISLNK(attrs.st_mode):
                raise ValueError("SFTP paths through symbolic links are not supported.")

    @staticmethod
    def _is_already_exists(error: OSError) -> bool:
        return getattr(error, "errno", None) in {
            errno.EEXIST,
            80,  # Windows ERROR_FILE_EXISTS
            183,  # Windows ERROR_ALREADY_EXISTS
        } or "exist" in str(error).casefold()

    @staticmethod
    def _remote_item_exists(sftp: object, remote_path: str) -> bool:
        try:
            sftp.lstat(remote_path)
        except OSError:
            return False
        return True

    @staticmethod
    def _verify_source(
        source: StorageProvider,
        relative_path: str,
        precondition: TransferPrecondition,
    ) -> None:
        source_record = source.get_record(relative_path)
        if (
            source_record is None
            or not source_record.storage_location.same_identity_as(
                precondition.source_location
            )
            or compare_snapshot(
                source_record.metadata,
                precondition.source_metadata,
                source.capabilities,
            )
            is not EvidenceMatch.MATCH
        ):
            raise TransferPreconditionFailed(
                TransferPreconditionTarget.SOURCE,
                "The source file changed after it was reviewed.",
            )


def _normalize_relative_path(relative_path: str) -> str:
    normalized = posixpath.normpath(relative_path.replace("\\", "/"))
    if (
        not relative_path
        or normalized in {"", ".", ".."}
        or normalized.startswith("../")
        or normalized.startswith("/")
    ):
        raise ValueError("A safe relative SFTP path is required.")
    return normalized


def _metadata_from_attrs(attrs: object) -> ComparisonMetadata:
    modified_time = getattr(attrs, "st_mtime", None)
    if modified_time is None:
        return ComparisonMetadata(size=attrs.st_size)
    return ComparisonMetadata(
        size=attrs.st_size,
        modified_time=float(modified_time),
        timestamp_reliable=True,
    )
