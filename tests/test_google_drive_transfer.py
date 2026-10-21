from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.google_drive_provider import GoogleDriveProvider
from core.local_storage_provider import LocalStorageProvider
from core.sync_service import SyncService
from core.sync_history_service import SyncHistoryService
from core.sync_history_store import JsonSyncHistoryStore
from core.sync_history_lock import SyncHistoryLock
from models.sync_direction import SyncDirection
from models.compare_status import CompareStatus


class GoogleTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / "local"; self.local.mkdir()
        self.content = b"synthetic reviewed content"
        api = Mock()
        api.files.return_value.get.return_value.execute.return_value = {
            "id":"root-id", "name":"Test", "mimeType":"application/vnd.google-apps.folder"}
        self.cloud = GoogleDriveProvider("root-id", "Test", "synthetic@example.invalid", service=api)
        self.record = self.cloud._to_record({"id": "file-id", "name": "new.txt",
            "mimeType": "application/octet-stream", "size": str(len(self.content)),
            "modifiedTime": "2030-01-01T00:00:00Z", "version": "1",
            "md5Checksum": hashlib.md5(self.content).hexdigest()}, "new.txt")
        self.cloud._records = {"new.txt": self.record}
        self.cloud.scan = Mock(return_value=dict(self.cloud._records))
        self.cloud._fetch_record = Mock(return_value=self.record)
        self.history = SyncHistoryService(JsonSyncHistoryStore(self.root / "history/runs"),
            lock_factory=lambda: SyncHistoryLock(self.root / "history/sync.lock"))
        self.service = SyncService(LocalStorageProvider(str(self.local), "Local"), self.cloud, history_service=self.history)

    def preview(self, direction=SyncDirection.SERVER_TO_LOCAL):
        return self.service.create_preview(self.service.compare(), direction)

    def run_job(self, preview):
        content = self.content
        class Downloader:
            def __init__(self, output, request):
                self.output = output
            def next_chunk(self):
                self.output.write(content)
                return None, True
        with patch("googleapiclient.http.MediaIoBaseDownload", Downloader):
            job = self.service.create_job(preview)
            worker = self.service.start_job(job, preview)
            worker.join(5)
            self.assertFalse(worker.is_alive())
        return job, self.history.get_record(job.history_run_id)

    def test_reviewed_download_publishes_new_file_and_records_history(self):
        preview = self.preview()
        self.assertEqual(preview.total_files, 1)
        job, history = self.run_job(preview)
        self.assertEqual((self.local / "new.txt").read_bytes(), self.content)
        self.assertEqual(job.copied_files, 1)
        self.assertEqual(history.counts.copied, 1)
        self.assertAlmostEqual((self.local / "new.txt").stat().st_mtime,self.record.modified_time,places=5)
        self.assertEqual(self.service.compare()[0].status,CompareStatus.SAME)

    def test_destination_appearing_after_review_is_preserved(self):
        preview = self.preview()
        (self.local / "new.txt").write_bytes(b"external")
        job, history = self.run_job(preview)
        self.assertEqual((self.local / "new.txt").read_bytes(), b"external")
        self.assertEqual(job.copied_files, 0)
        self.assertEqual(history.counts.copied, 0)

    def test_existing_destination_is_excluded_from_preview(self):
        (self.local / "new.txt").write_bytes(b"existing")
        preview = self.preview()
        self.assertEqual(preview.total_files, 0)
        self.assertTrue(any("replacement" in warning for warning in preview.warnings))

    def test_upload_is_excluded_even_with_a_local_source(self):
        (self.local / "upload.txt").write_bytes(b"local")
        preview = self.preview(SyncDirection.LOCAL_TO_SERVER)
        self.assertEqual(preview.total_files, 0)

    def test_changed_source_version_is_not_copied(self):
        preview = self.preview()
        self.cloud._fetch_record.return_value = replace(self.record,
            comparison_metadata=replace(self.record.metadata, version_id="changed"))
        job, history = self.run_job(preview)
        self.assertFalse((self.local / "new.txt").exists())
        self.assertEqual(job.copied_files, 0)
        self.assertEqual(history.counts.copied, 0)

    def test_empty_download_is_published_and_recorded_as_a_completed_copy(self):
        self.content = b""
        self.record = replace(self.record, size=0,
            comparison_metadata=replace(self.record.metadata, size=0,
                content_hash=hashlib.md5(b"").hexdigest()))
        self.cloud._records["new.txt"] = self.record
        self.cloud.scan.return_value = dict(self.cloud._records)
        self.cloud._fetch_record.return_value = self.record
        job, history = self.run_job(self.preview())
        self.assertEqual((self.local / "new.txt").read_bytes(), b"")
        self.assertEqual(job.copied_files, 1)
        self.assertEqual(history.counts.copied, 1)

    def test_forged_replacement_is_refused_even_on_a_direct_destination_call(self):
        from core.storage_provider import ConditionalTransferUnsupported
        from models.transfer_precondition import TransferPrecondition
        target = self.local / "new.txt"
        target.write_bytes(b"keep external bytes")
        destination = self.service.local_provider.get_record("new.txt")
        precondition = TransferPrecondition(self.record.storage_location, self.record.metadata,
            destination.storage_location, destination.metadata)
        with patch.object(self.cloud, "open_transfer_content") as download:
            with self.assertRaises(ConditionalTransferUnsupported):
                self.service.local_provider.transfer_from(self.cloud, "new.txt", precondition)
            download.assert_not_called()
        self.assertEqual(target.read_bytes(), b"keep external bytes")

    def test_cancel_before_start_records_unattempted_work_without_download(self):
        preview = self.preview()
        job = self.service.create_job(preview)
        job.request_cancel()
        with patch.object(self.cloud, "open_transfer_content") as download:
            worker = self.service.start_job(job, preview)
            worker.join(5)
            self.assertFalse(worker.is_alive())
            download.assert_not_called()
        history = self.history.get_record(job.history_run_id)
        self.assertTrue(job.summary().cancelled)
        self.assertEqual(history.counts.copied, 0)
        self.assertEqual(job.not_attempted_files, 1)
        self.assertFalse((self.local / "new.txt").exists())
