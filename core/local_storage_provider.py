import os
from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile

from core.storage_provider import ProviderCapability, StorageProvider
from models.backup_content import BackupContent
from models.comparison_metadata import ComparisonMetadata
from models.file_record import FileRecord
from models.storage_location import StorageLocation
from models.sync_history import StorageEndpointSnapshot


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
        return frozenset({ProviderCapability.TIMESTAMPS, ProviderCapability.METADATA})

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
        )

    def copy_from(self, source: StorageProvider, relative_path: str) -> None:
        if not isinstance(source, LocalStorageProvider):
            raise NotImplementedError("Copying from this storage provider is not supported yet.")

        source_path = source.location_for(relative_path).as_local_path()
        if not source_path.is_file():
            raise FileNotFoundError("The source file is no longer available.")

        self.replace_from_file(source_path, relative_path)

    def replace_from_file(self, source_path: Path, relative_path: str) -> None:
        """Copy to a sibling temporary file before atomically replacing the target."""
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
                raise ValueError("The source file changed while it was being copied.")
            os.replace(temporary_path, destination_path)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
