from core.storage_provider import StorageProvider
from models.file_record import FileRecord


class StorageScanner:
    """Provider-agnostic scanning entry point for future storage backends."""

    @staticmethod
    def scan(provider: StorageProvider) -> dict[str, FileRecord]:
        return provider.scan()
