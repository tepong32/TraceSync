import tempfile
import unittest
from pathlib import Path

from core.storage_provider import ProviderCapability, StorageProvider
from core.sync_history_lock import SyncHistoryLock
from core.sync_history_service import SyncHistoryService
from core.sync_history_store import JsonSyncHistoryStore
from core.sync_service import SyncService
from models.file_record import FileRecord
from models.sync_direction import SyncDirection
from models.sync_job import SyncJobStatus
from models.sync_history import (
    StorageEndpointSnapshot,
    SyncFileOutcome,
    SyncReasonCode,
    SyncRunOutcome,
)


class FakeStorageProvider(StorageProvider):
    def __init__(self, name, records=None, failing_paths=None):
        self.name = name
        self.records = records or {}
        self.failing_paths = failing_paths or set()
        self.copied_paths = []
        self.record_failure_paths = set()
        self.after_copy = None

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
        if relative_path in self.record_failure_paths:
            raise RuntimeError(relative_path)
        return self.records.get(relative_path)

    def destination_path(self, relative_path):
        return f"{self.name}/{relative_path}"

    def copy_from(self, source, relative_path):
        if relative_path in self.failing_paths:
            raise PermissionError(relative_path)
        self.copied_paths.append(relative_path)
        self.records[relative_path] = source.get_record(relative_path)
        if self.after_copy is not None:
            self.after_copy()


def record(path, modified_time):
    return FileRecord(path, path, modified_time, 1)


class SynchronizationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        history_root = Path(self.workspace.name) / "history"
        self.history_service = SyncHistoryService(
            JsonSyncHistoryStore(history_root / "runs"),
            version_provider=lambda: "0.9.0",
            lock_factory=lambda: SyncHistoryLock(history_root / "sync.lock"),
        )

    def make_service(self, local, server):
        return SyncService(local, server, history_service=self.history_service)

    def test_preview_selects_only_eligible_files(self):
        local = FakeStorageProvider("local", {
            "newer.txt": record("local/newer.txt", 20),
            "only-local.txt": record("local/only-local.txt", 20),
            "older.txt": record("local/older.txt", 10),
        })
        server = FakeStorageProvider("server", {
            "newer.txt": record("server/newer.txt", 10),
            "older.txt": record("server/older.txt", 20),
        })
        service = self.make_service(local, server)

        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)

        self.assertEqual([item.relative_path for item in preview.items], ["newer.txt", "only-local.txt"])
        self.assertEqual(preview.create_count, 1)
        self.assertEqual(preview.overwrite_count, 1)

    def test_job_executes_the_reviewed_preview(self):
        local = FakeStorageProvider("local", {"reports/july.txt": record("local/reports/july.txt", 100)})
        server = FakeStorageProvider("server")
        service = self.make_service(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(server.copied_paths, ["reports/july.txt"])
        self.assertEqual(job.status, SyncJobStatus.COMPLETED)
        self.assertEqual(job.copied_files, 1)
        self.assertEqual(job.file_outcomes[0].outcome, SyncFileOutcome.COPIED)

    def test_file_failure_does_not_stop_other_files(self):
        local = FakeStorageProvider("local", {
            "blocked.txt": record("local/blocked.txt", 20),
            "kept.txt": record("local/kept.txt", 20),
        })
        server = FakeStorageProvider("server", failing_paths={"blocked.txt"})
        service = self.make_service(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertEqual(server.copied_paths, ["kept.txt"])
        self.assertEqual(len(job.errors), 1)
        failed = next(result for result in job.file_outcomes if result.relative_path == "blocked.txt")
        self.assertEqual(failed.outcome, SyncFileOutcome.FAILED)
        self.assertEqual(failed.reason_code, SyncReasonCode.PERMISSION_DENIED)
        self.assertEqual(job.failed_files, 1)
        self.assertEqual(job.skipped_files, 0)
        history_record = self.history_service.list_records().records[0]
        self.assertEqual(history_record.outcome, SyncRunOutcome.COMPLETED_WITH_ISSUES)
        self.assertEqual(history_record.counts.failed, 1)

    def test_job_rejects_a_destination_that_changed_after_preview(self):
        local = FakeStorageProvider("local", {"report.txt": record("local/report.txt", 20)})
        server = FakeStorageProvider("server")
        service = self.make_service(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        server.records["report.txt"] = record("server/report.txt", 30)
        job = service.create_job(preview)

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertFalse(server.copied_paths)
        self.assertEqual(job.skipped_files, 1)
        self.assertEqual(job.file_outcomes[0].outcome, SyncFileOutcome.SKIPPED)
        self.assertEqual(job.file_outcomes[0].reason_code, SyncReasonCode.DESTINATION_APPEARED)
        history_record = self.history_service.list_records().records[0]
        self.assertEqual(history_record.outcome, SyncRunOutcome.COMPLETED_WITH_ISSUES)
        self.assertEqual(history_record.counts.skipped, 1)

    def test_job_rejects_a_source_that_changed_after_preview(self):
        local = FakeStorageProvider("local", {"report.txt": record("local/report.txt", 20)})
        server = FakeStorageProvider("server")
        service = self.make_service(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        local.records["report.txt"] = record("local/report.txt", 30)
        job = service.create_job(preview)

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertFalse(server.copied_paths)
        self.assertEqual(job.skipped_files, 1)
        self.assertEqual(job.file_outcomes[0].outcome, SyncFileOutcome.SKIPPED)
        self.assertEqual(job.file_outcomes[0].reason_code, SyncReasonCode.SOURCE_CHANGED)

    def test_requested_cancellation_prevents_the_next_file_from_copying(self):
        local = FakeStorageProvider("local", {"report.txt": record("local/report.txt", 20)})
        server = FakeStorageProvider("server")
        service = self.make_service(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)
        job.request_cancel()

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.CANCELLED)
        self.assertFalse(server.copied_paths)
        self.assertEqual(job.not_attempted_files, 1)
        self.assertEqual(job.file_outcomes[0].outcome, SyncFileOutcome.NOT_ATTEMPTED)
        self.assertEqual(job.file_outcomes[0].reason_code, SyncReasonCode.CANCELLED)

    def test_cancellation_after_partial_completion_records_remaining_files(self):
        local = FakeStorageProvider("local", {
            "a.txt": record("local/a.txt", 20),
            "b.txt": record("local/b.txt", 20),
        })
        server = FakeStorageProvider("server")
        service = self.make_service(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)
        server.after_copy = job.request_cancel

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.CANCELLED)
        self.assertEqual(server.copied_paths, ["a.txt"])
        self.assertEqual(
            [result.outcome for result in job.file_outcomes],
            [SyncFileOutcome.COPIED, SyncFileOutcome.NOT_ATTEMPTED],
        )
        history_record = self.history_service.list_records().records[0]
        self.assertEqual(history_record.outcome, SyncRunOutcome.CANCELLED)
        self.assertEqual(history_record.counts.not_attempted, 1)

    def test_run_level_failure_preserves_copy_and_marks_remaining_files(self):
        local = FakeStorageProvider("local", {
            "a.txt": record("local/a.txt", 20),
            "b.txt": record("local/b.txt", 20),
            "c.txt": record("local/c.txt", 20),
        })
        server = FakeStorageProvider("server")
        service = self.make_service(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)
        local.record_failure_paths.add("b.txt")

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.FAILED)
        self.assertEqual(server.copied_paths, ["a.txt"])
        self.assertEqual(
            [result.outcome for result in job.file_outcomes],
            [
                SyncFileOutcome.COPIED,
                SyncFileOutcome.NOT_ATTEMPTED,
                SyncFileOutcome.NOT_ATTEMPTED,
            ],
        )
        self.assertTrue(
            all(
                result.reason_code is SyncReasonCode.RUN_FAILED
                for result in job.file_outcomes[1:]
            )
        )
        history_record = self.history_service.list_records().records[0]
        self.assertEqual(history_record.outcome, SyncRunOutcome.FAILED)
        self.assertEqual(history_record.counts.copied, 1)
        self.assertEqual(history_record.counts.not_attempted, 2)
