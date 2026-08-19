from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol
from uuid import uuid4

from core.storage_provider import StorageProvider
from core.sync_history_lock import SyncAlreadyActiveError, SyncHistoryLock
from core.sync_history_export import export_sync_run_csv
from core.sync_history_store import (
    HistoryLoadResult,
    JsonSyncHistoryStore,
    SyncHistoryStore,
)
from models.sync_history import (
    SyncFileOutcome,
    SyncFileOutcomeRecord,
    SyncReasonCode,
    SyncRunCounts,
    SyncRunOutcome,
    SyncRunRecord,
    utc_timestamp,
)
from models.sync_job import SyncJob, SyncJobStatus
from models.sync_preview import SyncPreview
from utils.application_version import get_application_version


class HistoryPersistenceError(RuntimeError):
    """Raised when the durable initial history precondition cannot be met."""


class RunLock(Protocol):
    def acquire(self) -> None: ...

    def release(self) -> None: ...


@dataclass(slots=True)
class SyncRunContext:
    initial_record: SyncRunRecord
    run_lock: RunLock


@dataclass(frozen=True, slots=True)
class HistoryRecoveryResult:
    recovered_runs: int
    failed_runs: int
    lock_unavailable: bool = False


class SyncHistoryService:
    """Creates and finalizes durable records around synchronization execution."""

    def __init__(
        self,
        store: SyncHistoryStore | None = None,
        *,
        version_provider: Callable[[], str] = get_application_version,
        now_provider: Callable[[], datetime] | None = None,
        run_id_provider: Callable[[], str] | None = None,
        lock_factory: Callable[[], RunLock] | None = None,
    ) -> None:
        self.store = store or JsonSyncHistoryStore()
        self.version_provider = version_provider
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.run_id_provider = run_id_provider or (lambda: str(uuid4()))
        self.lock_factory = lock_factory or self._default_lock_factory()

    def begin_run(
        self,
        preview: SyncPreview,
        source_provider: StorageProvider,
        destination_provider: StorageProvider,
    ) -> SyncRunContext:
        if not preview.items:
            raise ValueError("An empty synchronization preview cannot create a history run.")

        run_lock = self.lock_factory()
        run_lock.acquire()
        try:
            initial_record = self._build_initial_record(
                preview,
                source_provider,
                destination_provider,
            )
            self.store.create(initial_record)
        except Exception as exc:
            run_lock.release()
            if isinstance(exc, ValueError):
                raise
            raise HistoryPersistenceError(
                "TraceSync could not create the synchronization history record. No files were copied."
            ) from exc
        return SyncRunContext(initial_record=initial_record, run_lock=run_lock)

    def finalize_run(self, context: SyncRunContext, job: SyncJob) -> None:
        try:
            terminal_record = self._build_terminal_record(context.initial_record, job)
            self.store.replace(terminal_record)
        except Exception as exc:
            with job.lock:
                job.history_finalization_error = (
                    "Synchronization finished, but TraceSync could not finalize its history record."
                )
                job.history_finalization_exception = exc
        else:
            try:
                self.store.apply_retention(protected_run_id=terminal_record.run_id)
            except Exception:
                with job.lock:
                    job.history_maintenance_warning = (
                        "Synchronization history was saved, but old history cleanup could not finish."
                    )
        finally:
            context.run_lock.release()

    def recover_interrupted_runs(self) -> HistoryRecoveryResult:
        recovery_lock = self.lock_factory()
        try:
            recovery_lock.acquire()
        except SyncAlreadyActiveError:
            return HistoryRecoveryResult(0, 0, lock_unavailable=True)
        except Exception:
            return HistoryRecoveryResult(0, 1)

        recovered = 0
        failed = 0
        try:
            try:
                loaded = self.store.list_records()
            except Exception:
                return HistoryRecoveryResult(0, 1)
            for record in loaded.records:
                if record.outcome is not SyncRunOutcome.IN_PROGRESS:
                    continue
                try:
                    self.store.replace(self._as_interrupted(record))
                    recovered += 1
                except Exception:
                    failed += 1
            if recovered:
                try:
                    self.store.apply_retention()
                except Exception:
                    failed += 1
        finally:
            recovery_lock.release()
        return HistoryRecoveryResult(recovered, failed)

    def list_records(self, limit: int | None = None) -> HistoryLoadResult:
        return self.store.list_records(limit=limit)

    def get_record(self, run_id: str) -> SyncRunRecord | None:
        return self.store.get(run_id)

    def clear_history(self) -> int:
        clear_lock = self.lock_factory()
        clear_lock.acquire()
        try:
            return self.store.clear()
        finally:
            clear_lock.release()

    def export_run(self, run_id: str, destination: Path) -> None:
        record = self.store.get(run_id)
        if record is None:
            raise ValueError("The selected synchronization history record no longer exists.")
        export_sync_run_csv(record, destination)

    def _build_initial_record(
        self,
        preview: SyncPreview,
        source_provider: StorageProvider,
        destination_provider: StorageProvider,
    ) -> SyncRunRecord:
        files = tuple(
            SyncFileOutcomeRecord(
                relative_path=item.relative_path,
                operation=item.operation.value.lower(),
                overwrite=item.overwrite,
                outcome=SyncFileOutcome.PENDING,
            )
            for item in preview.items
        )
        return SyncRunRecord(
            run_id=self.run_id_provider(),
            application_version=self.version_provider(),
            outcome=SyncRunOutcome.IN_PROGRESS,
            started_at_utc=utc_timestamp(self.now_provider()),
            finished_at_utc=None,
            duration_ms=None,
            direction=preview.direction,
            source=source_provider.describe_endpoint(),
            destination=destination_provider.describe_endpoint(),
            counts=SyncRunCounts(
                planned=len(files),
                planned_overwrites=sum(item.overwrite for item in files),
            ),
            files=files,
        )

    def _build_terminal_record(
        self,
        initial_record: SyncRunRecord,
        job: SyncJob,
    ) -> SyncRunRecord:
        summary = job.summary()
        if len(summary.file_outcomes) != initial_record.counts.planned:
            raise ValueError("Every approved file must have a terminal outcome.")
        return replace(
            initial_record,
            outcome=self._run_outcome(job.status),
            finished_at_utc=utc_timestamp(self.now_provider()),
            duration_ms=round(summary.elapsed_seconds * 1000),
            counts=SyncRunCounts(
                planned=initial_record.counts.planned,
                planned_overwrites=initial_record.counts.planned_overwrites,
                copied=summary.copied_files,
                overwritten=summary.overwritten_files,
                skipped=summary.skipped_files,
                failed=summary.failed_files,
                not_attempted=summary.not_attempted_files,
            ),
            files=summary.file_outcomes,
        )

    @staticmethod
    def _run_outcome(status: SyncJobStatus) -> SyncRunOutcome:
        outcomes = {
            SyncJobStatus.COMPLETED: SyncRunOutcome.COMPLETED,
            SyncJobStatus.COMPLETED_WITH_ERRORS: SyncRunOutcome.COMPLETED_WITH_ISSUES,
            SyncJobStatus.CANCELLED: SyncRunOutcome.CANCELLED,
            SyncJobStatus.FAILED: SyncRunOutcome.FAILED,
        }
        try:
            return outcomes[status]
        except KeyError as exc:
            raise ValueError("Synchronization job is not in a terminal state.") from exc

    @staticmethod
    def _as_interrupted(record: SyncRunRecord) -> SyncRunRecord:
        interrupted_files = tuple(
            replace(
                item,
                outcome=SyncFileOutcome.UNKNOWN,
                reason_code=SyncReasonCode.INTERRUPTED,
                message=(
                    "TraceSync cannot confirm this file's outcome because the synchronization history was interrupted."
                ),
            )
            for item in record.files
        )
        return replace(
            record,
            outcome=SyncRunOutcome.INTERRUPTED,
            finished_at_utc=None,
            duration_ms=None,
            counts=SyncRunCounts(
                planned=record.counts.planned,
                planned_overwrites=record.counts.planned_overwrites,
                unknown=len(interrupted_files),
            ),
            files=interrupted_files,
        )

    def _default_lock_factory(self) -> Callable[[], RunLock]:
        history_directory = getattr(self.store, "history_directory", None)
        if history_directory is None:
            raise ValueError("A lock factory is required for a history store without a filesystem path.")
        lock_path = Path(history_directory).parent / "sync.lock"
        return lambda: SyncHistoryLock(lock_path)
