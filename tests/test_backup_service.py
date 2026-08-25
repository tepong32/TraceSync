import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.backup_service import BackupService
from core.backup_store import JsonBackupStore
from core.local_storage_provider import LocalStorageProvider
from core.sync_history_lock import SyncHistoryLock
from core.sync_history_service import SyncHistoryService
from core.sync_history_store import JsonSyncHistoryStore
from core.sync_service import SyncService
from models.sync_direction import SyncDirection
from models.sync_history import SyncFileOutcome, SyncReasonCode
from models.sync_job import SyncJobStatus


class BackupIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.local_root = self.root / "local"
        self.server_root = self.root / "server"
        self.local_root.mkdir()
        self.server_root.mkdir()
        history_root = self.root / "history"
        self.history_service = SyncHistoryService(
            JsonSyncHistoryStore(history_root / "runs"),
            lock_factory=lambda: SyncHistoryLock(history_root / "sync.lock"),
        )
        self.backup_store = JsonBackupStore(self.root / "backups")
        self.backup_service = BackupService(self.backup_store)

    def make_service(self) -> SyncService:
        return SyncService(
            LocalStorageProvider(str(self.local_root), "Local Folder"),
            LocalStorageProvider(str(self.server_root), "Server Folder"),
            history_service=self.history_service,
            backup_service=self.backup_service,
        )

    @staticmethod
    def write_version(path: Path, content: str, modified_time: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        os.utime(path, (modified_time, modified_time))

    def run_local_to_server(self, service: SyncService):
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)
        service.start_job(job, preview).join(timeout=5)
        return job

    def test_overwrite_creates_restorable_backup_linked_from_history(self):
        local_file = self.local_root / "report.txt"
        server_file = self.server_root / "report.txt"
        self.write_version(local_file, "new version", 200)
        self.write_version(server_file, "old version", 100)
        service = self.make_service()

        job = self.run_local_to_server(service)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED)
        self.assertEqual(server_file.read_text(encoding="utf-8"), "new version")
        outcome = job.file_outcomes[0]
        self.assertEqual(outcome.outcome, SyncFileOutcome.COPIED)
        self.assertIsNotNone(outcome.backup_id)
        stored = self.backup_store.get(outcome.backup_id)
        self.assertEqual(stored.content_path.read_text(encoding="utf-8"), "old version")
        history = self.history_service.get_record(job.history_run_id)
        self.assertEqual(history.files[0].backup_id, outcome.backup_id)
        self.assertEqual(
            self.backup_service.backup_ids_for_run(job.history_run_id)["report.txt"],
            outcome.backup_id,
        )

        result = self.backup_service.restore(outcome.backup_id)

        self.assertEqual(server_file.read_text(encoding="utf-8"), "old version")
        self.assertIsNotNone(result.safety_backup_id)
        safety = self.backup_store.get(result.safety_backup_id)
        self.assertEqual(safety.content_path.read_text(encoding="utf-8"), "new version")

        undo_result = self.backup_service.restore(outcome.backup_id)

        self.assertEqual(undo_result.restored_backup_id, result.safety_backup_id)
        self.assertEqual(server_file.read_text(encoding="utf-8"), "new version")
        self.assertIsNone(self.backup_store.get(outcome.backup_id))

        redo_result = self.backup_service.restore(outcome.backup_id)

        self.assertEqual(redo_result.restored_backup_id, undo_result.safety_backup_id)
        self.assertEqual(server_file.read_text(encoding="utf-8"), "old version")

    def test_new_file_copy_does_not_create_a_backup(self):
        self.write_version(self.local_root / "new.txt", "new file", 200)
        service = self.make_service()

        job = self.run_local_to_server(service)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED)
        self.assertIsNone(job.file_outcomes[0].backup_id)
        self.assertFalse(tuple(self.backup_store.records_directory.glob("*.json")))

    def test_backup_failure_blocks_the_overwrite(self):
        local_file = self.local_root / "report.txt"
        server_file = self.server_root / "report.txt"
        self.write_version(local_file, "new version", 200)
        self.write_version(server_file, "old version", 100)
        service = self.make_service()

        with patch.object(self.backup_store, "create", side_effect=OSError("disk full")):
            job = self.run_local_to_server(service)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertEqual(server_file.read_text(encoding="utf-8"), "old version")
        self.assertEqual(job.file_outcomes[0].outcome, SyncFileOutcome.FAILED)
        self.assertEqual(job.file_outcomes[0].reason_code, SyncReasonCode.BACKUP_FAILED)

    def test_destination_change_after_backup_is_not_overwritten(self):
        local_file = self.local_root / "report.txt"
        server_file = self.server_root / "report.txt"
        self.write_version(local_file, "new version", 200)
        self.write_version(server_file, "old version", 100)
        service = self.make_service()
        real_create = self.backup_store.create

        def change_after_backup(record, source_path):
            real_create(record, source_path)
            self.write_version(server_file, "external edit", 300)

        with patch.object(self.backup_store, "create", side_effect=change_after_backup):
            job = self.run_local_to_server(service)

        self.assertEqual(server_file.read_text(encoding="utf-8"), "external edit")
        outcome = job.file_outcomes[0]
        self.assertEqual(outcome.outcome, SyncFileOutcome.SKIPPED)
        self.assertEqual(outcome.reason_code, SyncReasonCode.DESTINATION_CHANGED)
        self.assertIsNotNone(outcome.backup_id)

    def test_atomic_replace_failure_preserves_destination_and_backup(self):
        local_file = self.local_root / "report.txt"
        server_file = self.server_root / "report.txt"
        self.write_version(local_file, "new version", 200)
        self.write_version(server_file, "old version", 100)
        service = self.make_service()
        real_replace = os.replace

        def fail_destination_replace(source, destination):
            if Path(destination).resolve() == server_file.resolve():
                raise PermissionError("locked")
            return real_replace(source, destination)

        with patch("core.local_storage_provider.os.replace", side_effect=fail_destination_replace):
            job = self.run_local_to_server(service)

        self.assertEqual(server_file.read_text(encoding="utf-8"), "old version")
        outcome = job.file_outcomes[0]
        self.assertEqual(outcome.outcome, SyncFileOutcome.FAILED)
        self.assertEqual(outcome.reason_code, SyncReasonCode.PERMISSION_DENIED)
        self.assertIsNotNone(outcome.backup_id)
        self.assertIsNotNone(self.backup_store.get(outcome.backup_id))
        self.assertFalse(tuple(self.server_root.glob(".report.txt.*.tmp")))


class BackupStoreTests(unittest.TestCase):
    @staticmethod
    def make_clock(count: int):
        start = datetime(2026, 8, 25, tzinfo=timezone.utc)
        values = iter(start + timedelta(seconds=index) for index in range(count))
        return lambda: next(values)

    def test_retention_keeps_the_newest_backup_and_its_content(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            destination_root = root / "destination"
            destination_root.mkdir()
            destination = destination_root / "file.txt"
            destination.write_text("first", encoding="utf-8")
            provider = LocalStorageProvider(str(destination_root), "Destination")
            store = JsonBackupStore(root / "backups", retention_limit=1)
            ids = iter(
                (
                    "00000000-0000-0000-0000-000000000001",
                    "00000000-0000-0000-0000-000000000002",
                )
            )
            service = BackupService(store, id_provider=lambda: next(ids))
            first = service.create_backup(
                provider,
                "file.txt",
                "10000000-0000-0000-0000-000000000001",
            )
            destination.write_text("second", encoding="utf-8")
            second = service.create_backup(
                provider,
                "file.txt",
                "10000000-0000-0000-0000-000000000002",
            )

            self.assertIsNone(store.get(first.backup_id))
            self.assertIsNotNone(store.get(second.backup_id))

    def test_retention_keeps_only_two_versions_of_the_same_destination_file(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            destination_root = root / "destination"
            destination_root.mkdir()
            destination = destination_root / "report.txt"
            provider = LocalStorageProvider(str(destination_root), "Destination")
            store = JsonBackupStore(root / "backups")
            service = BackupService(store, now_provider=self.make_clock(3))
            records = []

            for version in range(3):
                destination.write_text(f"version {version}", encoding="utf-8")
                os.utime(destination, (version + 1, version + 1))
                records.append(
                    service.create_backup(
                        provider,
                        "report.txt",
                        str(uuid4()),
                    )
                )

            self.assertIsNone(store.get(records[0].backup_id))
            self.assertIsNotNone(store.get(records[1].backup_id))
            self.assertIsNotNone(store.get(records[2].backup_id))
            self.assertEqual(len(tuple(store.records_directory.glob("*.json"))), 2)

    def test_size_limit_deletes_oldest_backups_first(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            destination_root = root / "destination"
            destination_root.mkdir()
            provider = LocalStorageProvider(str(destination_root), "Destination")
            store = JsonBackupStore(
                root / "backups",
                per_file_retention_limit=10,
                size_limit_bytes=10,
            )
            service = BackupService(store, now_provider=self.make_clock(3))
            records = []

            for index in range(3):
                relative_path = f"file-{index}.txt"
                destination = destination_root / relative_path
                destination.write_text("12345", encoding="utf-8")
                records.append(
                    service.create_backup(provider, relative_path, str(uuid4()))
                )

            self.assertIsNone(store.get(records[0].backup_id))
            self.assertIsNotNone(store.get(records[1].backup_id))
            self.assertIsNotNone(store.get(records[2].backup_id))

    def test_same_relative_path_in_different_destinations_is_retained_separately(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            first_root = root / "first"
            second_root = root / "second"
            first_root.mkdir()
            second_root.mkdir()
            (first_root / "report.txt").write_text("first", encoding="utf-8")
            (second_root / "report.txt").write_text("second", encoding="utf-8")
            store = JsonBackupStore(
                root / "backups",
                per_file_retention_limit=1,
            )
            service = BackupService(store, now_provider=self.make_clock(2))

            first = service.create_backup(
                LocalStorageProvider(str(first_root), "First"),
                "report.txt",
                str(uuid4()),
            )
            second = service.create_backup(
                LocalStorageProvider(str(second_root), "Second"),
                "report.txt",
                str(uuid4()),
            )

            self.assertIsNotNone(store.get(first.backup_id))
            self.assertIsNotNone(store.get(second.backup_id))

    def test_current_oversized_backup_is_protected(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            destination_root = root / "destination"
            destination_root.mkdir()
            destination = destination_root / "large.bin"
            destination.write_bytes(b"12345")
            provider = LocalStorageProvider(str(destination_root), "Destination")
            store = JsonBackupStore(root / "backups", size_limit_bytes=4)
            service = BackupService(store)

            current = service.create_backup(provider, "large.bin", str(uuid4()))

            self.assertIsNotNone(store.get(current.backup_id))


if __name__ == "__main__":
    unittest.main()
