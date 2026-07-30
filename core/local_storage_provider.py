from pathlib import Path
import shutil

from core.storage_provider import ProviderCapability, StorageProvider
from models.file_record import FileRecord


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
                records[relative_path] = FileRecord(
                    absolute_path=str(file_path.resolve()),
                    relative_path=relative_path,
                    modified_time=stat.st_mtime,
                    size=stat.st_size,
                )
            except (OSError, PermissionError):
                continue
        return records

    def destination_path(self, relative_path: str) -> str:
        candidate = (self.root / Path(relative_path)).resolve()
        root = self.root.resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("The file path is outside the selected folder.")
        return str(candidate)

    def get_record(self, relative_path: str) -> FileRecord | None:
        file_path = Path(self.destination_path(relative_path))
        try:
            if not file_path.is_file():
                return None
            stat = file_path.stat()
            return FileRecord(
                absolute_path=str(file_path.resolve()),
                relative_path=relative_path,
                modified_time=stat.st_mtime,
                size=stat.st_size,
            )
        except (OSError, PermissionError):
            return None

    def copy_from(self, source: StorageProvider, relative_path: str) -> None:
        if not isinstance(source, LocalStorageProvider):
            raise NotImplementedError("Copying from this storage provider is not supported yet.")

        source_path = Path(source.destination_path(relative_path))
        destination_path = Path(self.destination_path(relative_path))
        if not source_path.is_file():
            raise FileNotFoundError("The source file is no longer available.")

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
