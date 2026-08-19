from core.comparer import compare_folders
from core.ignore.ignore_engine import create_ignore_engine
from core.local_storage_provider import LocalStorageProvider
from core.storage_provider import StorageProvider
from core.storage_scanner import StorageScanner
from core.sync_history_service import SyncHistoryService
from models.compare_status import CompareStatus
from models.comparison_result import ComparisonResult
from models.sync_direction import SyncDirection
from models.sync_preview import SyncOperation, SyncPreview, SyncPreviewItem


class SyncExecutionStartError(RuntimeError):
    """Raised when a durable run exists but its worker cannot start."""



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
        history_service: SyncHistoryService | None = None,
    ) -> None:
        if local_provider is not None and source_provider is not None:
            raise ValueError("Specify either local_provider or source_provider, not both.")
        if server_provider is not None and destination_provider is not None:
            raise ValueError("Specify either server_provider or destination_provider, not both.")
        self.local_provider = source_provider or local_provider
        self.server_provider = destination_provider or server_provider
        self.history_service = history_service or SyncHistoryService()
        # Created when compare() knows the project root.
        self._ignore_engine: IgnoreRuleEngine | None = None
        self.last_ignored_count = 0

    def compare(
        self,
        local_folder: str | None = None,
        server_folder: str | None = None,
        *,
        user_ignore_patterns: list[str] | None = None,
    ) -> list[ComparisonResult]:
        """Scan both providers once and return their comparison results."""
        if local_folder is not None or server_folder is not None:
            if not local_folder or not server_folder:
                raise ValueError("Both folders are required for comparison.")

            self.local_provider = LocalStorageProvider(
                local_folder,
                "Local Folder",
            )
            self.server_provider = LocalStorageProvider(
                server_folder,
                "Server Folder",
            )

        local_provider, server_provider = self._providers()

        # Build a configured ignore engine for this project.
        self._ignore_engine = create_ignore_engine(
            getattr(local_provider, "root", local_folder or "."),
            user_ignore_patterns=user_ignore_patterns,
        )

        local_files, local_ignored = StorageScanner.scan_with_ignored_count(
            local_provider,
            self._ignore_engine,
        )

        server_files, server_ignored = StorageScanner.scan_with_ignored_count(
            server_provider,
            self._ignore_engine,
        )
        self.last_ignored_count = local_ignored + server_ignored

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
                    decision_recommendation=(result.decision.recommendation if result.decision else None),
                    decision_confidence=(result.decision.confidence.value if result.decision else None),
                    decision_reason=(result.decision.reason if result.decision else None),
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
        history_context = self.history_service.begin_run(preview, source, destination)
        with job.lock:
            job.history_run_id = history_context.initial_record.run_id
        try:
            return SyncJobRunner(source, destination).run_async(
                job,
                preview,
                on_finished=lambda finished_job: self.history_service.finalize_run(
                    history_context,
                    finished_job,
                ),
            )
        except Exception as exc:
            self._mark_job_start_failed(job, preview)
            self.history_service.finalize_run(history_context, job)
            with job.lock:
                job.completion_ready = True
            raise SyncExecutionStartError(
                "Synchronization could not start. No files were copied."
            ) from exc

    def recover_interrupted_history(self):
        return self.history_service.recover_interrupted_runs()

    @staticmethod
    def _mark_job_start_failed(job, preview: SyncPreview) -> None:
        from time import monotonic

        from models.sync_history import (
            SyncFileOutcome,
            SyncFileOutcomeRecord,
            SyncReasonCode,
        )
        from models.sync_job import SyncError, SyncJobStatus

        timestamp = monotonic()
        with job.lock:
            job.status = SyncJobStatus.FAILED
            job.started_at = timestamp
            job.finished_at = timestamp
            job.errors.append(
                SyncError("", "Synchronization could not start its background worker.")
            )
            job.file_outcomes = [
                SyncFileOutcomeRecord(
                    relative_path=item.relative_path,
                    operation=item.operation.value.lower(),
                    overwrite=item.overwrite,
                    outcome=SyncFileOutcome.NOT_ATTEMPTED,
                    reason_code=SyncReasonCode.RUN_FAILED,
                    message="Synchronization stopped before this file could be attempted.",
                )
                for item in preview.items
            ]
            job.not_attempted_files = len(job.file_outcomes)

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
