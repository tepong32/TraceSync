import os
import tempfile
import unittest
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch
from uuid import uuid4

from core.backup_service import BackupCreationError, BackupService
from core.backup_store import JsonBackupStore
from core.local_storage_provider import LocalStorageProvider
from core.storage_provider import ProviderCapability, StorageProvider
from core.sync_history_lock import SyncAlreadyActiveError, SyncHistoryLock
from core.sync_history_service import SyncHistoryService
from core.sync_history_store import JsonSyncHistoryStore
from core.sync_service import SyncService
from models.backup_content import BackupContent
from models.backup_record import BackupRecord
from models.comparison_metadata import ComparisonMetadata
from models.file_record import FileRecord
from models.storage_location import StorageLocation
from models.sync_direction import SyncDirection
from models.sync_history import (
    StorageEndpointSnapshot,
    SyncFileOutcome,
    SyncReasonCode,
)
from models.sync_job import SyncJobStatus


class MaterializedBackupProvider(StorageProvider):
    """Test-only seam for provider content materialized on local storage."""

    def __init__(
        self,
        content_path: Path,
        *,
        backup_available: bool = True,
        comparison_metadata: ComparisonMetadata | None = None,
    ) -> None:
        self.content_path = content_path
        self.backup_available = backup_available
        self.copied_paths: list[str] = []
        stat = content_path.stat()
        metadata = comparison_metadata or ComparisonMetadata(
            size=stat.st_size,
            modified_time=stat.st_mtime,
            timestamp_reliable=True,
        )
        self.record = FileRecord.from_location(
            StorageLocation("test-provider", "item-1", "Remote/report.txt"),
            "report.txt",
            metadata.modified_time,
            stat.st_size,
            comparison_metadata=metadata,
        )

    @property
    def display_name(self):
        return "Test Destination"

    @property
    def capabilities(self):
        return frozenset(
            {
                ProviderCapability.TIMESTAMPS,
                ProviderCapability.CONDITIONAL_TRANSFER,
            }
        )

    def describe_endpoint(self):
        return StorageEndpointSnapshot(
            "test-provider",
            self.display_name,
            "account/root",
        )

    def scan(self):
        return {"report.txt": self.record}

    def get_record(self, relative_path):
        return self.record if relative_path == "report.txt" else None

    def location_for(self, relative_path):
        return self.record.storage_location

    def open_backup_content(self, relative_path):
        if not self.backup_available:
            raise OSError("materialization failed")
        stat = self.content_path.stat()
        return nullcontext(
            BackupContent(
                local_path=self.content_path,
                size=stat.st_size,
                modified_time=stat.st_mtime,
                comparison_metadata=self.record.metadata,
            )
        )

    def transfer_from(self, source, relative_path, precondition):
        self.copied_paths.append(relative_path)


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

        with (
            patch.object(
                self.backup_store,
                "create",
                side_effect=OSError("disk full"),
            ),
            patch.object(
                service.server_provider,
                "transfer_from",
                wraps=service.server_provider.transfer_from,
            ) as transfer,
        ):
            job = self.run_local_to_server(service)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertEqual(server_file.read_text(encoding="utf-8"), "old version")
        self.assertEqual(job.file_outcomes[0].outcome, SyncFileOutcome.FAILED)
        self.assertEqual(job.file_outcomes[0].reason_code, SyncReasonCode.BACKUP_FAILED)
        transfer.assert_not_called()

    def test_backup_is_durable_before_conditional_transfer_starts(self):
        local_file = self.local_root / "report.txt"
        server_file = self.server_root / "report.txt"
        self.write_version(local_file, "new version", 200)
        self.write_version(server_file, "old version", 100)
        service = self.make_service()
        transfer_observations: list[bool] = []
        real_transfer = service.server_provider.transfer_from

        def observe_backup_before_transfer(source, relative_path, precondition):
            transfer_observations.append(
                bool(tuple(self.backup_store.records_directory.glob("*.json")))
            )
            return real_transfer(source, relative_path, precondition)

        with patch.object(
            service.server_provider,
            "transfer_from",
            side_effect=observe_backup_before_transfer,
        ):
            job = self.run_local_to_server(service)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED)
        self.assertEqual(transfer_observations, [True])

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

    def test_conditional_transfer_rejects_change_after_final_runner_validation(self):
        local_file = self.local_root / "report.txt"
        server_file = self.server_root / "report.txt"
        self.write_version(local_file, "new version", 200)
        self.write_version(server_file, "old version", 100)
        service = self.make_service()
        real_transfer = service.server_provider.transfer_from

        def change_at_transfer_boundary(source, relative_path, precondition):
            self.write_version(server_file, "last-moment edit", 300)
            return real_transfer(source, relative_path, precondition)

        with patch.object(
            service.server_provider,
            "transfer_from",
            side_effect=change_at_transfer_boundary,
        ):
            job = self.run_local_to_server(service)

        outcome = job.file_outcomes[0]
        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertEqual(outcome.outcome, SyncFileOutcome.SKIPPED)
        self.assertEqual(outcome.reason_code, SyncReasonCode.DESTINATION_CHANGED)
        self.assertIsNotNone(outcome.backup_id)
        self.assertEqual(server_file.read_text(encoding="utf-8"), "last-moment edit")

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

    def test_restore_is_blocked_while_synchronization_holds_the_shared_lock(self):
        local_file = self.local_root / "report.txt"
        server_file = self.server_root / "report.txt"
        self.write_version(local_file, "new version", 200)
        self.write_version(server_file, "old version", 100)
        service = self.make_service()
        completed_job = self.run_local_to_server(service)
        backup_id = completed_job.file_outcomes[0].backup_id
        self.write_version(local_file, "newest version", 300)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        context = self.history_service.begin_run(
            preview,
            service.local_provider,
            service.server_provider,
        )

        try:
            with self.assertRaises(SyncAlreadyActiveError):
                self.backup_service.restore(backup_id)
        finally:
            context.run_lock.release()

        self.assertEqual(server_file.read_text(encoding="utf-8"), "new version")
        self.backup_service.restore(backup_id)
        self.assertEqual(server_file.read_text(encoding="utf-8"), "old version")

    def test_active_restore_blocks_synchronization_and_another_restore(self):
        local_file = self.local_root / "report.txt"
        server_file = self.server_root / "report.txt"
        self.write_version(local_file, "new version", 200)
        self.write_version(server_file, "old version", 100)
        service = self.make_service()
        completed_job = self.run_local_to_server(service)
        backup_id = completed_job.file_outcomes[0].backup_id
        self.write_version(local_file, "newest version", 300)
        preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
        job = service.create_job(preview)
        restore_entered = Event()
        allow_restore = Event()
        restore_errors: list[Exception] = []
        real_restore = self.backup_service._restore

        def blocking_restore(selected_backup_id):
            restore_entered.set()
            if not allow_restore.wait(timeout=5):
                raise TimeoutError("The restore test did not resume.")
            return real_restore(selected_backup_id)

        def run_restore():
            try:
                self.backup_service.restore(backup_id)
            except Exception as exc:
                restore_errors.append(exc)

        with patch.object(self.backup_service, "_restore", side_effect=blocking_restore):
            restore_thread = Thread(target=run_restore)
            restore_thread.start()
            self.assertTrue(restore_entered.wait(timeout=5))
            try:
                with self.assertRaises(SyncAlreadyActiveError):
                    service.start_job(job, preview)
                with self.assertRaises(SyncAlreadyActiveError):
                    self.backup_service.restore(backup_id)
            finally:
                allow_restore.set()
                restore_thread.join(timeout=5)

        self.assertFalse(restore_thread.is_alive())
        self.assertEqual(restore_errors, [])
        self.assertEqual(server_file.read_text(encoding="utf-8"), "old version")

    def test_restore_exception_releases_the_shared_lock(self):
        local_file = self.local_root / "report.txt"
        server_file = self.server_root / "report.txt"
        self.write_version(local_file, "new version", 200)
        self.write_version(server_file, "old version", 100)
        service = self.make_service()
        completed_job = self.run_local_to_server(service)
        backup_id = completed_job.file_outcomes[0].backup_id

        with patch.object(self.backup_service, "_restore", side_effect=OSError("restore failed")):
            with self.assertRaises(OSError):
                self.backup_service.restore(backup_id)

        self.backup_service.restore(backup_id)
        self.assertEqual(server_file.read_text(encoding="utf-8"), "old version")


class BackupProviderBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.materialized_content = self.root / "materialized-report.txt"
        self.materialized_content.write_text("existing remote content", encoding="utf-8")
        os.utime(self.materialized_content, (100, 100))
        self.backup_store = JsonBackupStore(self.root / "backups")
        self.backup_service = BackupService(self.backup_store)

    def test_provider_materialized_content_is_saved_in_local_backup_store(self):
        provider = MaterializedBackupProvider(self.materialized_content)

        record = self.backup_service.create_backup(
            provider,
            "report.txt",
            str(uuid4()),
        )

        stored = self.backup_store.get(record.backup_id)
        self.assertIsNotNone(stored)
        self.assertEqual(
            stored.content_path.read_text(encoding="utf-8"),
            "existing remote content",
        )
        self.assertEqual(record.destination.provider_type, "test-provider")

    def test_remote_comparison_metadata_is_separate_from_local_materialization(self):
        local_stat = self.materialized_content.stat()
        provider_metadata = ComparisonMetadata(
            size=local_stat.st_size,
            version_id="remote-version-1",
        )
        provider = MaterializedBackupProvider(
            self.materialized_content,
            comparison_metadata=provider_metadata,
        )

        record = self.backup_service.create_backup(
            provider,
            "report.txt",
            str(uuid4()),
        )

        self.assertIsNone(record.original_modified_time)
        self.assertEqual(
            record.materialized_modified_time,
            local_stat.st_mtime,
        )
        self.assertEqual(BackupRecord.from_dict(record.to_dict()), record)
        self.assertIsNotNone(self.backup_store.get(record.backup_id))

    def test_provider_materialization_failure_is_a_backup_failure(self):
        provider = MaterializedBackupProvider(
            self.materialized_content,
            backup_available=False,
        )

        with self.assertRaises(BackupCreationError):
            self.backup_service.create_backup(
                provider,
                "report.txt",
                str(uuid4()),
            )

        self.assertFalse(tuple(self.backup_store.records_directory.glob("*.json")))

    def test_failed_destination_protection_prevents_overwrite(self):
        source_root = self.root / "source"
        source_root.mkdir()
        source_file = source_root / "report.txt"
        source_file.write_text("new local content", encoding="utf-8")
        os.utime(source_file, (200, 200))
        destination = MaterializedBackupProvider(
            self.materialized_content,
            backup_available=False,
        )
        history_root = self.root / "history"
        history_service = SyncHistoryService(
            JsonSyncHistoryStore(history_root / "runs"),
            lock_factory=lambda: SyncHistoryLock(history_root / "sync.lock"),
        )
        service = SyncService(
            LocalStorageProvider(str(source_root), "Source"),
            destination,
            history_service=history_service,
            backup_service=self.backup_service,
        )
        preview = service.create_preview(
            service.compare(),
            SyncDirection.LOCAL_TO_SERVER,
        )
        job = service.create_job(preview)

        service.start_job(job, preview).join(timeout=5)

        self.assertEqual(job.status, SyncJobStatus.COMPLETED_WITH_ERRORS)
        self.assertEqual(job.file_outcomes[0].reason_code, SyncReasonCode.BACKUP_FAILED)
        self.assertEqual(destination.copied_paths, [])
        self.assertFalse(tuple(self.backup_store.records_directory.glob("*.json")))


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
