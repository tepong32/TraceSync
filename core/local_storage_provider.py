import os
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile

from core.comparison_evidence import EvidenceMatch, compare_snapshot
from core.local_file_commit import publish_new_file
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


class LocalStorageProvider(StorageProvider):
    """A filesystem-backed storage provider for local and mapped-drive paths."""

    def __init__(self, root_path: str, display_name: str) -> None:
        self.root = Path(root_path)
        self._display_name = display_name

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def capabilities(self) -> frozenset[ProviderCapability]:
        return frozenset(
            {
                ProviderCapability.TIMESTAMPS,
                ProviderCapability.METADATA,
                ProviderCapability.CONDITIONAL_CREATE,
                # Legacy overwrite workflow retained by explicit product
                # decision: check + os.replace is not atomic compare-and-swap.
                # See docs/ARCHITECTURE.md, Local overwrite limitation.
                ProviderCapability.CONDITIONAL_TRANSFER,
            }
        )

    def describe_endpoint(self) -> StorageEndpointSnapshot:
        return StorageEndpointSnapshot(
            provider_type="local",
            display_name=self.display_name,
            locator=str(self.root.resolve()),
        )

    def scan(self) -> dict[str, FileRecord]:
        if not self.root.exists():
            raise FileNotFoundError(f"Folder does not exist: {self.root}")
        if not self.root.is_dir():
            raise NotADirectoryError(f"Not a directory: {self.root}")

        records: dict[str, FileRecord] = {}
        for file_path in self.root.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                stat = file_path.stat()
                relative_path = file_path.relative_to(self.root).as_posix()
                location = StorageLocation.local(file_path)
                records[relative_path] = FileRecord.from_location(
                    location=location,
                    relative_path=relative_path,
                    modified_time=stat.st_mtime,
                    size=stat.st_size,
                    comparison_metadata=ComparisonMetadata(
                        size=stat.st_size,
                        modified_time=stat.st_mtime,
                        timestamp_reliable=True,
                    ),
                )
            except (OSError, PermissionError):
                continue
        return records

    def location_for(self, relative_path: str) -> StorageLocation:
        candidate = (self.root / Path(relative_path)).resolve()
        root = self.root.resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("The file path is outside the selected folder.")
        return StorageLocation.local(candidate, resolve=False)

    def get_record(self, relative_path: str) -> FileRecord | None:
        location = self.location_for(relative_path)
        file_path = location.as_local_path()
        try:
            if not file_path.is_file():
                return None
            stat = file_path.stat()
            return FileRecord.from_location(
                location=location,
                relative_path=relative_path,
                modified_time=stat.st_mtime,
                size=stat.st_size,
                comparison_metadata=ComparisonMetadata(
                    size=stat.st_size,
                    modified_time=stat.st_mtime,
                    timestamp_reliable=True,
                ),
            )
        except (OSError, PermissionError):
            return None

    @contextmanager
    def open_backup_content(self, relative_path: str):
        local_path = self.location_for(relative_path).as_local_path()
        if not local_path.is_file():
            raise FileNotFoundError("The destination file is no longer available for backup.")
        stat = local_path.stat()
        yield BackupContent(
            local_path=local_path,
            size=stat.st_size,
            modified_time=stat.st_mtime,
            comparison_metadata=ComparisonMetadata(
                size=stat.st_size,
                modified_time=stat.st_mtime,
                timestamp_reliable=True,
            ),
        )

    @contextmanager
    def open_transfer_content(
        self,
        relative_path: str,
        precondition: TransferPrecondition,
    ):
        self._verify_source_precondition(self, relative_path, precondition)
        local_path = precondition.source_location.as_local_path()
        if not local_path.is_file():
            raise TransferPreconditionFailed(
                TransferPreconditionTarget.SOURCE,
                "The source file is no longer available.",
            )
        stat = local_path.stat()
        yield BackupContent(
            local_path=local_path,
            size=stat.st_size,
            modified_time=stat.st_mtime,
            comparison_metadata=precondition.source_metadata,
        )

    def transfer_from(
        self,
        source: StorageProvider,
        relative_path: str,
        precondition: TransferPrecondition,
    ) -> None:
        if source.create_only and not precondition.expects_destination_absent:
            raise ConditionalTransferUnsupported("This source permits new-file transfers only.")
        self._verify_transfer_precondition(source, relative_path, precondition)
        with source.open_transfer_content(relative_path, precondition) as content:
            self.replace_from_file(
                content.local_path,
                relative_path,
                source_provider=source,
                precondition=precondition,
            )

    def replace_from_file(
        self,
        source_path: Path,
        relative_path: str,
        *,
        source_provider: StorageProvider | None = None,
        precondition: TransferPrecondition | None = None,
    ) -> None:
        """Stage content, then publish exclusively or replace an existing file.

        Reviewed absence is enforced by the publication operation itself.
        Existing-file replacement retains a check-to-replace race; callers
        must preserve the backup protection and documented concurrency limit.
        """
        destination_path = self.location_for(relative_path).as_local_path()
        if not source_path.is_file():
            raise FileNotFoundError("The source file is no longer available.")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            source_stat = source_path.stat()
            with tempfile.NamedTemporaryFile(
                prefix=f".{destination_path.name}.",
                suffix=".tmp",
                dir=destination_path.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            shutil.copy2(source_path, temporary_path)
            with temporary_path.open("r+b") as copied_file:
                os.fsync(copied_file.fileno())
            final_source_stat = source_path.stat()
            temporary_stat = temporary_path.stat()
            if (
                source_stat.st_size != final_source_stat.st_size
                or source_stat.st_mtime != final_source_stat.st_mtime
                or temporary_stat.st_size != final_source_stat.st_size
                or temporary_stat.st_mtime != final_source_stat.st_mtime
            ):
                if precondition is not None:
                    raise TransferPreconditionFailed(
                        TransferPreconditionTarget.SOURCE,
                        "The source file changed while it was being copied.",
                    )
                raise ValueError("The source file changed while it was being copied.")
            if precondition is not None and source_provider is not None:
                self._verify_transfer_precondition(
                    source_provider,
                    relative_path,
                    precondition,
                )
            if precondition is not None and precondition.expects_destination_absent:
                try:
                    publish_new_file(temporary_path, destination_path)
                except FileExistsError as exc:
                    raise TransferPreconditionFailed(
                        TransferPreconditionTarget.DESTINATION,
                        "A destination file appeared after the transfer was reviewed.",
                    ) from exc
            else:
                os.replace(temporary_path, destination_path)
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    # Cleanup must not hide a precondition failure or turn an
                    # already committed copy into a reported transfer failure.
                    pass

    def _verify_transfer_precondition(
        self,
        source: StorageProvider,
        relative_path: str,
        precondition: TransferPrecondition,
    ) -> None:
        if not self.location_for(relative_path).same_identity_as(
            precondition.destination_location
        ):
            raise TransferPreconditionFailed(
                TransferPreconditionTarget.DESTINATION,
                "The transfer destination does not match the reviewed location.",
            )

        self._verify_source_precondition(source, relative_path, precondition)

        destination_record = self.get_record(relative_path)
        if precondition.expects_destination_absent:
            if destination_record is not None:
                raise TransferPreconditionFailed(
                    TransferPreconditionTarget.DESTINATION,
                    "A destination file appeared after the transfer was reviewed.",
                )
            return

        if (
            destination_record is None
            or not destination_record.storage_location.same_identity_as(
                precondition.destination_location
            )
            or compare_snapshot(
                destination_record.metadata,
                precondition.destination_metadata,
                self.capabilities,
            )
            is not EvidenceMatch.MATCH
        ):
            raise TransferPreconditionFailed(
                TransferPreconditionTarget.DESTINATION,
                "The destination file changed after it was reviewed.",
            )

    @staticmethod
    def _verify_source_precondition(
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
