import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.backup_service import BackupService
from core.backup_store import JsonBackupStore
from core.local_file_commit import publish_new_file
from core.local_storage_provider import LocalStorageProvider
from core.sync_history_lock import SyncHistoryLock
from core.sync_history_service import SyncHistoryService
from core.sync_history_store import JsonSyncHistoryStore
from core.sync_service import SyncService
from models.sync_direction import SyncDirection
from models.sync_history import SyncFileOutcome, SyncReasonCode


class LocalTransferRaceHistoryTests(unittest.TestCase):
    def test_late_destination_is_skipped_once_and_other_files_continue(self):
        # Earlier UI tests can leave Tk objects in cycles. Dispose of them on
        # their owning thread before this test starts a filesystem worker.
        gc.collect()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root, destination_root = root / "source", root / "destination"
            source_root.mkdir()
            destination_root.mkdir()
            for name in ("collision.txt", "safe.txt"):
                (source_root / name).write_text("reviewed source", encoding="utf-8")
            history = SyncHistoryService(
                JsonSyncHistoryStore(root / "history" / "runs"),
                lock_factory=lambda: SyncHistoryLock(root / "history" / "sync.lock"),
            )
            backups = BackupService(JsonBackupStore(root / "backups"))
            service = SyncService(
                LocalStorageProvider(str(source_root), "Source"),
                LocalStorageProvider(str(destination_root), "Destination"),
                history_service=history,
                backup_service=backups,
            )
            preview = service.create_preview(service.compare(), SyncDirection.LOCAL_TO_SERVER)
            job = service.create_job(preview)

            def publish_after_external_create(staged, destination):
                if destination.name == "collision.txt":
                    destination.write_text("external edit", encoding="utf-8")
                publish_new_file(staged, destination)

            with patch(
                "core.local_storage_provider.publish_new_file",
                side_effect=publish_after_external_create,
            ) as publish:
                worker = service.start_job(job, preview)
                worker.join(timeout=5)
                if worker.is_alive():
                    job.request_cancel()
                    worker.join(timeout=30)
                self.assertFalse(worker.is_alive())

            self.assertEqual(publish.call_count, 2)  # No automatic retry.
            self.assertEqual(job.copied_files, 1)
            self.assertEqual(job.skipped_files, 1)
            self.assertEqual(job.failed_files, 0)
            self.assertEqual(
                (destination_root / "collision.txt").read_text(encoding="utf-8"),
                "external edit",
            )
            self.assertEqual(
                (destination_root / "safe.txt").read_text(encoding="utf-8"),
                "reviewed source",
            )
            self.assertEqual(sorted(p.name for p in destination_root.iterdir()),
                             ["collision.txt", "safe.txt"])
            record = history.get_record(job.history_run_id)
            collision = next(item for item in record.files if item.relative_path == "collision.txt")
            self.assertEqual(collision.outcome, SyncFileOutcome.SKIPPED)
            self.assertEqual(collision.reason_code, SyncReasonCode.DESTINATION_APPEARED)
            self.assertIsNone(collision.backup_id)
            self.assertEqual(record.counts.copied, 1)
            self.assertEqual(record.counts.skipped, 1)
