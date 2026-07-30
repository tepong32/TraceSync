from threading import Thread
from time import monotonic

from core.storage_provider import StorageProvider
from models.sync_job import SyncError, SyncJob, SyncJobStatus
from models.sync_preview import SyncPreview


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

        for item in preview.items:
            with job.lock:
                if job.cancellation_requested:
                    job.status = SyncJobStatus.CANCELLED
                    break
                job.current_file = item.relative_path
            try:
                self._validate_preview_item(item)
                self.destination_provider.copy_from(self.source_provider, item.relative_path)
                with job.lock:
                    job.copied_files += 1
                    if item.overwrite:
                        job.overwritten_files += 1
            except (OSError, PermissionError, ValueError, NotImplementedError) as exc:
                with job.lock:
                    job.skipped_files += 1
                    job.errors.append(SyncError(item.relative_path, self._friendly_error(exc)))
            except Exception:
                with job.lock:
                    job.skipped_files += 1
                    job.errors.append(SyncError(item.relative_path, "An unexpected error prevented this file from being copied."))
            finally:
                with job.lock:
                    job.completed_files += 1

        with job.lock:
            job.finished_at = monotonic()
            job.current_file = ""
            if job.status is SyncJobStatus.RUNNING:
                job.status = SyncJobStatus.COMPLETED_WITH_ERRORS if job.errors else SyncJobStatus.COMPLETED
        return job

    def _validate_preview_item(self, item) -> None:
        """Reject files that changed after the user reviewed the preview."""
        source_record = self.source_provider.get_record(item.relative_path)
        if source_record is None:
            raise FileNotFoundError(item.relative_path)
        if (
            source_record.modified_time != item.source_modified_time
            or source_record.size != item.source_size
        ):
            raise ValueError("The source file changed after the preview was created.")

        destination_record = self.destination_provider.get_record(item.relative_path)
        if not item.overwrite and destination_record is not None:
            raise ValueError("A destination file appeared after the preview was created.")
        if item.overwrite and destination_record is not None and (
            destination_record.modified_time != item.destination_modified_time
            or destination_record.size != item.destination_size
        ):
            raise ValueError("The destination file changed after the preview was created.")

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
