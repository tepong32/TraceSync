from core.ignore_rule_engine import IgnoreRuleEngine
from core.storage_provider import StorageProvider
from models.file_record import FileRecord


class StorageScanner:
    """
    Provider-agnostic scanning entry point.

    A StorageProvider is responsible for discovering files.

    The StorageScanner is responsible for preparing the scan results
    before they enter the comparison pipeline.
    """

    @staticmethod
    def scan(
        provider: StorageProvider,
        ignore_engine: IgnoreRuleEngine | None = None,
    ) -> dict[str, FileRecord]:
        """
        Scan a provider and optionally filter ignored files.
        """

        files = provider.scan()

        if ignore_engine is None:
            return files

        return {
            relative_path: record
            for relative_path, record in files.items()
            if not ignore_engine.is_ignored(relative_path)
        }