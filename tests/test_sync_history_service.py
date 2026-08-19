import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.storage_provider import ProviderCapability, StorageProvider
from core.sync_history_lock import SyncAlreadyActiveError, SyncHistoryLock
from core.sync_history_service import HistoryPersistenceError, SyncHistoryService
from core.sync_history_store import JsonSyncHistoryStore
from core.sync_service import SyncService
from core.sync_service import SyncExecutionStartError
from models.file_record import FileRecord
from models.sync_direction import SyncDirection
from models.sync_history import (
    StorageEndpointSnapshot,
    SyncFileOutcome,
    SyncRunOutcome,
)
from models.sync_job import SyncJobStatus


class TrackingProvider(StorageProvider):
    def __init__(self, name: str, records=None) -> None:
        self.name = name
        self.records = records or {}
        self.copied_paths: list[str] = []
        self.secret_token = "must-not-be-persisted"

    @property
    def display_name(self):
        return self.name

    @property
    def capabilities(self):
        return frozenset({ProviderCapability.TIMESTAMPS})

    def describe_endpoint(self):
        return StorageEndpointSnapshot("fake", self.name, self.name)

    def scan(self):
        return self.records

    def get_record(self, relative_path):
        return self.records.get(relative_path)

    def destination_path(self, relative_path):
        return f"{self.name}/{relative_path}"

    def copy_from(self, source, relative_path):
        self.copied_paths.append(relative_path)
        self.records[relative_path] = source.get_record(relative_path)


def file_record(provider_name: str, relative_path: str) -> FileRecord:
    return FileRecord(
        absolute_path=f"{provider_name}/{relative_path}",
        relative_path=relative_path,
        modified_time=100,
        size=10,
    )


class SyncHistoryLockTests(unittest.TestCase):
    def test_only_one_lock_can_be_held(self):
        with tempfile.TemporaryDirectory() as workspace:
            lock_path = Path(workspace) / "sync.lock"
            first = SyncHistoryLock(lock_path)
            second = SyncHistoryLock(lock_path)
            first.acquire()
            self.addCleanup(first.release)

            with self.assertRaises(SyncAlreadyActiveError):
                second.acquire()

            first.release()
            second.acquire()
            second.release()


class SyncHistoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.history_root = Path(self.workspace.name) / "history"
        self.store = JsonSyncHistoryStore(self.history_root / "runs")
        self.history_service = SyncHistoryService(
            self.store,
            version_provider=lambda: "0.8.5",
            lock_factory=lambda: SyncHistoryLock(self.history_root / "sync.lock"),
        )
        self.local = TrackingProvider(
            "local",
            {"report.txt": file_record("local", "report.txt")},
        )
        self.server = TrackingProvider("server")

    def make_operation(self):
        service = SyncService(
            self.local,
            self.server,
            history_service=self.history_service,
        )
        preview = service.create_preview(
            service.compare(),
            SyncDirection.LOCAL_TO_SERVER,
        )
        return service, preview, service.create_job(preview)

    def test_successful_run_creates_one_final_record(self):
        service, preview, job = self.make_operation()

        service.start_job(job, preview).join(timeout=5)

        loaded = self.store.list_records()
        self.assertEqual(len(loaded.records), 1)
        record = loaded.records[0]
        self.assertEqual(record.run_id, job.history_run_id)
        self.assertEqual(record.application_version, "0.8.5")
        self.assertEqual(record.outcome, SyncRunOutcome.COMPLETED)
        self.assertEqual(record.counts.copied, 1)
        self.assertEqual(record.files[0].outcome, SyncFileOutcome.COPIED)
        self.assertEqual(job.status, SyncJobStatus.COMPLETED)
        self.assertTrue(job.completion_ready)
        persisted_payload = next((self.history_root / "runs").glob("*.json")).read_text(encoding="utf-8")
        self.assertNotIn(self.local.secret_token, persisted_payload)
        self.assertNotIn(self.server.secret_token, persisted_payload)

    def test_initial_history_failure_prevents_copying(self):
        service, preview, job = self.make_operation()

        with patch.object(self.store, "create", side_effect=OSError("disk full")):
            with self.assertRaises(HistoryPersistenceError):
                service.start_job(job, preview)

        self.assertFalse(self.server.copied_paths)
        self.assertEqual(job.status, SyncJobStatus.PENDING)
        self.assertFalse(tuple((self.history_root / "runs").glob("*.json")))

    def test_final_history_failure_does_not_falsify_execution_result(self):
        service, preview, job = self.make_operation()

        with patch.object(self.store, "replace", side_effect=OSError("locked")):
            service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED)
        self.assertEqual(self.server.copied_paths, ["report.txt"])
        self.assertIsNotNone(job.history_finalization_error)
        self.assertTrue(job.completion_ready)
        durable_record = self.store.get(job.history_run_id)
        self.assertIsNotNone(durable_record)
        self.assertEqual(durable_record.outcome, SyncRunOutcome.IN_PROGRESS)

        recovery = self.history_service.recover_interrupted_runs()

        self.assertEqual(recovery.recovered_runs, 1)
        self.assertEqual(
            self.store.get(job.history_run_id).outcome,
            SyncRunOutcome.INTERRUPTED,
        )

    def test_retention_failure_does_not_falsify_finalized_history(self):
        service, preview, job = self.make_operation()

        with patch.object(self.store, "apply_retention", side_effect=OSError("locked")):
            service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED)
        self.assertIsNone(job.history_finalization_error)
        self.assertIsNotNone(job.history_maintenance_warning)
        self.assertEqual(
            self.store.get(job.history_run_id).outcome,
            SyncRunOutcome.COMPLETED,
        )

    def test_worker_start_failure_is_finalized_without_copying(self):
        service, preview, job = self.make_operation()

        with patch(
            "core.sync_job_runner.SyncJobRunner.run_async",
            side_effect=RuntimeError("thread unavailable"),
        ):
            with self.assertRaises(SyncExecutionStartError):
                service.start_job(job, preview)

        self.assertFalse(self.server.copied_paths)
        self.assertEqual(job.status, SyncJobStatus.FAILED)
        self.assertTrue(job.completion_ready)
        record = self.store.get(job.history_run_id)
        self.assertEqual(record.outcome, SyncRunOutcome.FAILED)
        self.assertEqual(record.files[0].outcome, SyncFileOutcome.NOT_ATTEMPTED)

    def test_interrupted_recovery_marks_pending_files_unknown(self):
        service, preview, _job = self.make_operation()
        context = self.history_service.begin_run(preview, self.local, self.server)
        context.run_lock.release()

        result = self.history_service.recover_interrupted_runs()

        self.assertEqual(result.recovered_runs, 1)
        recovered = self.store.get(context.initial_record.run_id)
        self.assertEqual(recovered.outcome, SyncRunOutcome.INTERRUPTED)
        self.assertIsNone(recovered.finished_at_utc)
        self.assertIsNone(recovered.duration_ms)
        self.assertEqual(recovered.files[0].outcome, SyncFileOutcome.UNKNOWN)

    def test_busy_lock_prevents_history_creation_and_copying(self):
        service, preview, job = self.make_operation()
        active_lock = SyncHistoryLock(self.history_root / "sync.lock")
        active_lock.acquire()
        self.addCleanup(active_lock.release)

        with self.assertRaises(SyncAlreadyActiveError):
            service.start_job(job, preview)

        self.assertFalse(self.server.copied_paths)
        self.assertFalse(tuple((self.history_root / "runs").glob("*.json")))

    def test_recovery_defers_while_another_sync_holds_lock(self):
        _service, preview, _job = self.make_operation()
        context = self.history_service.begin_run(preview, self.local, self.server)

        result = self.history_service.recover_interrupted_runs()

        self.assertTrue(result.lock_unavailable)
        self.assertEqual(
            self.store.get(context.initial_record.run_id).outcome,
            SyncRunOutcome.IN_PROGRESS,
        )
        context.run_lock.release()

    def test_empty_preview_does_not_create_history(self):
        service = SyncService(
            self.local,
            self.server,
            history_service=self.history_service,
        )
        preview = service.create_preview([], SyncDirection.LOCAL_TO_SERVER)

        with self.assertRaises(ValueError):
            self.history_service.begin_run(preview, self.local, self.server)

        self.assertFalse(tuple((self.history_root / "runs").glob("*.json")))
