from threading import Thread
from time import monotonic

from core.storage_provider import StorageProvider
from models.sync_history import (
    SyncFileOutcome,
    SyncFileOutcomeRecord,
    SyncReasonCode,
)
from models.sync_job import SyncError, SyncJob, SyncJobStatus
from models.sync_preview import SyncPreview


class _SafetySkip(Exception):
    def __init__(self, reason_code: SyncReasonCode, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


class SyncJobRunner:
    """Executes approved previews independently of the Tkinter interface."""

    def __init__(self, source_provider: StorageProvider, destination_provider: StorageProvider) -> None:
        self.source_provider = source_provider
        self.destination_provider = destination_provider

    def run_async(self, job: SyncJob, preview: SyncPreview) -> Thread:
        thread = Thread(target=self.run, args=(job, preview), daemon=True)
        thread.start()
        return thread

    def run(self, job: SyncJob, preview: SyncPreview) -> SyncJob:
        with job.lock:
            job.status = SyncJobStatus.RUNNING
            job.started_at = monotonic()

        next_item_index = 0
        try:
            for item_index, item in enumerate(preview.items):
                next_item_index = item_index
                with job.lock:
                    if job.cancellation_requested:
                        job.status = SyncJobStatus.CANCELLED
                        break
                    job.current_file = item.relative_path
                self._run_item(job, item)
                next_item_index = item_index + 1
        except Exception:
            with job.lock:
                job.status = SyncJobStatus.FAILED
                job.errors.append(
                    SyncError("", "An unexpected problem stopped synchronization before it could finish.")
                )
            self._record_not_attempted(
                job,
                preview.items[next_item_index:],
                SyncReasonCode.RUN_FAILED,
                "Synchronization stopped before this file could be attempted.",
            )
        finally:
            with job.lock:
                if job.status is SyncJobStatus.CANCELLED:
                    remaining_items = preview.items[next_item_index:]
                else:
                    remaining_items = ()
            if remaining_items:
                self._record_not_attempted(
                    job,
                    remaining_items,
                    SyncReasonCode.CANCELLED,
                    "The user cancelled synchronization before this file was attempted.",
                )
            with job.lock:
                job.finished_at = monotonic()
                job.current_file = ""
                if job.status is SyncJobStatus.RUNNING:
                    job.status = (
                        SyncJobStatus.COMPLETED_WITH_ERRORS
                        if job.skipped_files or job.failed_files
                        else SyncJobStatus.COMPLETED
                    )
        return job

    def _run_item(self, job: SyncJob, item) -> None:
        try:
            self._validate_preview_item(item)
        except _SafetySkip as exc:
            self._record_issue(
                job,
                item,
                SyncFileOutcome.SKIPPED,
                exc.reason_code,
                exc.message,
            )
            return

        try:
            self.destination_provider.copy_from(self.source_provider, item.relative_path)
        except Exception as exc:
            reason_code, message = self._copy_failure_details(exc)
            self._record_issue(
                job,
                item,
                SyncFileOutcome.FAILED,
                reason_code,
                message,
            )
            return

        with job.lock:
            job.copied_files += 1
            if item.overwrite:
                job.overwritten_files += 1
            job.file_outcomes.append(
                self._file_outcome(item, SyncFileOutcome.COPIED)
            )
            job.completed_files += 1

    def _record_issue(
        self,
        job: SyncJob,
        item,
        outcome: SyncFileOutcome,
        reason_code: SyncReasonCode,
        message: str,
    ) -> None:
        with job.lock:
            if outcome is SyncFileOutcome.SKIPPED:
                job.skipped_files += 1
            else:
                job.failed_files += 1
            job.errors.append(SyncError(item.relative_path, message))
            job.file_outcomes.append(
                self._file_outcome(item, outcome, reason_code, message)
            )
            job.completed_files += 1

    def _record_not_attempted(
        self,
        job: SyncJob,
        items,
        reason_code: SyncReasonCode,
        message: str,
    ) -> None:
        with job.lock:
            for item in items:
                job.file_outcomes.append(
                    self._file_outcome(
                        item,
                        SyncFileOutcome.NOT_ATTEMPTED,
                        reason_code,
                        message,
                    )
                )
                job.not_attempted_files += 1

    def _validate_preview_item(self, item) -> None:
        """Reject files that changed after the user reviewed the preview."""
        source_record = self.source_provider.get_record(item.relative_path)
        if source_record is None:
            raise _SafetySkip(
                SyncReasonCode.SOURCE_MISSING,
                "The source file is no longer available.",
            )
        if (
            source_record.modified_time != item.source_modified_time
            or source_record.size != item.source_size
        ):
            raise _SafetySkip(
                SyncReasonCode.SOURCE_CHANGED,
                "The source file changed after the preview was created. Compare again before copying.",
            )

        destination_record = self.destination_provider.get_record(item.relative_path)
        if not item.overwrite and destination_record is not None:
            raise _SafetySkip(
                SyncReasonCode.DESTINATION_APPEARED,
                "A destination file appeared after the preview was created. Compare again before copying.",
            )
        if item.overwrite and destination_record is not None and (
            destination_record.modified_time != item.destination_modified_time
            or destination_record.size != item.destination_size
        ):
            raise _SafetySkip(
                SyncReasonCode.DESTINATION_CHANGED,
                "The destination file changed after the preview was created. Compare again before copying.",
            )

    @staticmethod
    def _file_outcome(
        item,
        outcome: SyncFileOutcome,
        reason_code: SyncReasonCode | None = None,
        message: str | None = None,
    ) -> SyncFileOutcomeRecord:
        return SyncFileOutcomeRecord(
            relative_path=item.relative_path,
            operation=item.operation.value.lower(),
            overwrite=item.overwrite,
            outcome=outcome,
            reason_code=reason_code,
            message=message,
        )

    @classmethod
    def _copy_failure_details(cls, error: Exception) -> tuple[SyncReasonCode, str]:
        if isinstance(error, PermissionError):
            return SyncReasonCode.PERMISSION_DENIED, cls._friendly_error(error)
        if isinstance(error, NotImplementedError):
            return SyncReasonCode.PROVIDER_UNSUPPORTED, cls._friendly_error(error)
        if isinstance(error, OSError):
            return SyncReasonCode.COPY_ERROR, cls._friendly_error(error)
        return (
            SyncReasonCode.UNEXPECTED_ERROR,
            "An unexpected error prevented this file from being copied.",
        )

    @staticmethod
    def _friendly_error(error: Exception) -> str:
        if isinstance(error, PermissionError):
            return "Permission was denied. Check that the file is not locked and that you have access."
        if isinstance(error, FileNotFoundError):
            return "The source file is no longer available."
        if isinstance(error, NotADirectoryError):
            return "The selected destination folder is unavailable."
        if isinstance(error, ValueError):
            return "A file changed after the preview was created. Compare again before copying."
        return "The file could not be copied. Check the file and destination, then try again."
