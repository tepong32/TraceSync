from core.ignore.ignore_rule_engine import IgnoreRuleEngine
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
        if ignore_engine is None:
            return provider.scan()

        return StorageScanner.scan_with_ignored_count(provider, ignore_engine)[0]

    @staticmethod
    def scan_with_ignored_count(
        provider: StorageProvider,
        ignore_engine: IgnoreRuleEngine,
    ) -> tuple[dict[str, FileRecord], int]:
        """
        Scan a provider and return visible files plus ignored file count.
        """
        files = provider.scan()
        included: dict[str, FileRecord] = {}
        ignored_count = 0

        for relative_path, record in files.items():
            if ignore_engine.is_ignored(relative_path):
                ignored_count += 1
                continue
            included[relative_path] = record

        return included, ignored_count
