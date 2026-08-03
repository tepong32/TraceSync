from core.comparer import compare_folders
from core.ignore_rule_engine import IgnoreRuleEngine
from core.local_storage_provider import LocalStorageProvider
from core.storage_provider import StorageProvider
from core.storage_scanner import StorageScanner
from models.compare_status import CompareStatus
from models.comparison_result import ComparisonResult
from models.sync_direction import SyncDirection
from models.sync_preview import SyncOperation, SyncPreview, SyncPreviewItem



class SyncService:
    """
    High-level orchestration service for TraceSync.
    """

    def __init__(
        self,
        local_provider: StorageProvider | None = None,
        server_provider: StorageProvider | None = None,
        *,
        source_provider: StorageProvider | None = None,
        destination_provider: StorageProvider | None = None,
    ) -> None:
        if local_provider is not None and source_provider is not None:
            raise ValueError("Specify either local_provider or source_provider, not both.")
        if server_provider is not None and destination_provider is not None:
            raise ValueError("Specify either server_provider or destination_provider, not both.")
        self.local_provider = source_provider or local_provider
        self.server_provider = destination_provider or server_provider
        self._ignore_engine = IgnoreRuleEngine()

    def compare(self, local_folder: str | None = None, server_folder: str | None = None) -> list[ComparisonResult]:
        """Scan both providers once and return their comparison results."""
        if local_folder is not None or server_folder is not None:
            if not local_folder or not server_folder:
                raise ValueError("Both folders are required for comparison.")
            self.local_provider = LocalStorageProvider(local_folder, "Local Folder")
            self.server_provider = LocalStorageProvider(server_folder, "Server Folder")

        local_provider, server_provider = self._providers()
        local_files = StorageScanner.scan(
            local_provider,
            self._ignore_engine,
        )

        server_files = StorageScanner.scan(
            server_provider,
            self._ignore_engine,
        )
        return compare_folders(local_files, server_files)

    def create_preview(
        self,
        results: list[ComparisonResult],
        direction: SyncDirection,
    ) -> SyncPreview:
        """Create the complete copy plan without touching either provider."""
        _, destination, eligible_statuses = self._direction_context(direction)
        items: list[SyncPreviewItem] = []

        for result in results:
            if result.status not in eligible_statuses:
                continue
            source_record = (
                result.local_record
                if direction is SyncDirection.LOCAL_TO_SERVER
                else result.server_record
            )
            destination_record = (
                result.server_record
                if direction is SyncDirection.LOCAL_TO_SERVER
                else result.local_record
            )
            if source_record is None:
                continue
            overwrite = destination_record is not None
            items.append(
                SyncPreviewItem(
                    relative_path=result.relative_path,
                    source=source_record.absolute_path,
                    destination=destination.destination_path(result.relative_path),
                    direction=direction,
                    comparison_status=result.status,
                    operation=SyncOperation.COPY,
                    overwrite=overwrite,
                    reason=self._reason_for(result.status),
                    source_modified_time=source_record.modified_time,
                    source_size=source_record.size,
                    destination_modified_time=(destination_record.modified_time if destination_record else None),
                    destination_size=(destination_record.size if destination_record else None),
                )
            )

        warnings: list[str] = []
        overwrites = sum(item.overwrite for item in items)
        if overwrites:
            warnings.append(f"{overwrites} existing file(s) will be replaced.")
        if not items:
            warnings.append("No files need to be copied in this direction.")
        return SyncPreview(direction=direction, items=tuple(items), warnings=tuple(warnings))

    def create_job(self, preview: SyncPreview):
        """Build a job that can execute a previously reviewed preview."""
        from models.sync_job import SyncJob

        return SyncJob(total_files=preview.total_files)

    def start_job(self, job, preview: SyncPreview):
        """Start an approved job on a worker thread and return that thread."""
        from core.sync_job_runner import SyncJobRunner

        source, destination, _ = self._direction_context(preview.direction)
        return SyncJobRunner(source, destination).run_async(job, preview)

    def _providers(self) -> tuple[StorageProvider, StorageProvider]:
        if self.local_provider is None or self.server_provider is None:
            raise RuntimeError("Compare two folders before preparing synchronization.")
        return self.local_provider, self.server_provider

    def _direction_context(self, direction: SyncDirection):
        local_provider, server_provider = self._providers()
        if direction is SyncDirection.LOCAL_TO_SERVER:
            return local_provider, server_provider, {CompareStatus.LOCAL_NEWER, CompareStatus.LOCAL_ONLY}
        return server_provider, local_provider, {CompareStatus.SERVER_NEWER, CompareStatus.SERVER_ONLY}

    @staticmethod
    def _reason_for(status: CompareStatus) -> str:
        reasons = {
            CompareStatus.LOCAL_ONLY: "The file exists only in the Local folder.",
            CompareStatus.SERVER_ONLY: "The file exists only in the Server folder.",
            CompareStatus.LOCAL_NEWER: "The Local copy is newer than the Server copy.",
            CompareStatus.SERVER_NEWER: "The Server copy is newer than the Local copy.",
        }
        return reasons[status]
