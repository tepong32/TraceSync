import unittest

from core.storage_provider import ProviderCapability, StorageProvider
from core.sync_service import SyncService
from models.file_record import FileRecord
from models.sync_direction import SyncDirection
from models.sync_job import SyncJobStatus


class FakeStorageProvider(StorageProvider):
    def __init__(self, name, records=None, failing_paths=None):
        self.name = name
        self.records = records or {}
        self.failing_paths = failing_paths or set()
        self.copied_paths = []

    @property
    def display_name(self):
        return self.name

    @property
    def capabilities(self):
        return frozenset({ProviderCapability.TIMESTAMPS})

    def scan(self):
        return self.records

    def get_record(self, relative_path):
        return self.records.get(relative_path)

    def destination_path(self, relative_path):
        return f"{self.name}/{relative_path}"

    def copy_from(self, source, relative_path):
        if relative_path in self.failing_paths:
            raise PermissionError(relative_path)
        self.copied_paths.append(relative_path)
        self.records[relative_path] = source.get_record(relative_path)


def record(path, modified_time):
    return FileRecord(path, path, modified_time, 1)


class SynchronizationTests(unittest.TestCase):
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
        service = SyncService(local, server)

        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)

        self.assertEqual([item.relative_path for item in preview.items], ["newer.txt", "only-local.txt"])
        self.assertEqual(preview.create_count, 1)
        self.assertEqual(preview.overwrite_count, 1)

    def test_job_executes_the_reviewed_preview(self):
        local = FakeStorageProvider("local", {"reports/july.txt": record("local/reports/july.txt", 100)})
        server = FakeStorageProvider("server")
        service = SyncService(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(server.copied_paths, ["reports/july.txt"])
        self.assertEqual(job.status, SyncJobStatus.COMPLETED)
        self.assertEqual(job.copied_files, 1)

    def test_file_failure_does_not_stop_other_files(self):
        local = FakeStorageProvider("local", {
            "blocked.txt": record("local/blocked.txt", 20),
            "kept.txt": record("local/kept.txt", 20),
        })
        server = FakeStorageProvider("server", failing_paths={"blocked.txt"})
        service = SyncService(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertEqual(server.copied_paths, ["kept.txt"])
        self.assertEqual(len(job.errors), 1)

    def test_job_rejects_a_destination_that_changed_after_preview(self):
        local = FakeStorageProvider("local", {"report.txt": record("local/report.txt", 20)})
        server = FakeStorageProvider("server")
        service = SyncService(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        server.records["report.txt"] = record("server/report.txt", 30)
        job = service.create_job(preview)

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertFalse(server.copied_paths)
        self.assertEqual(job.skipped_files, 1)

    def test_job_rejects_a_source_that_changed_after_preview(self):
        local = FakeStorageProvider("local", {"report.txt": record("local/report.txt", 20)})
        server = FakeStorageProvider("server")
        service = SyncService(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        local.records["report.txt"] = record("local/report.txt", 30)
        job = service.create_job(preview)

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertFalse(server.copied_paths)
        self.assertEqual(job.skipped_files, 1)

    def test_requested_cancellation_prevents_the_next_file_from_copying(self):
        local = FakeStorageProvider("local", {"report.txt": record("local/report.txt", 20)})
        server = FakeStorageProvider("server")
        service = SyncService(local, server)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)
        job.request_cancel()

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.CANCELLED)
        self.assertFalse(server.copied_paths)
