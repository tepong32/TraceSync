import gc
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from urllib.parse import unquote

from core.onedrive_provider import OneDriveProvider
from core.local_storage_provider import LocalStorageProvider
from core.sync_service import SyncService
from core.sync_job_runner import SyncJobRunner
from core.storage_provider import TransferFailed
from core.sync_history_service import SyncHistoryService
from core.sync_history_store import JsonSyncHistoryStore
from core.sync_history_lock import SyncHistoryLock
from models.sync_direction import SyncDirection
from models.sync_history import SyncReasonCode


def item(name, data=b"remote", **changes):
    return dict(id="id-" + name, name=name, size=len(data), file={}, eTag="v1",
                lastModifiedDateTime="2026-10-18T00:00:00Z", parentReference={"id": "root"},
                **{"@microsoft.graph.downloadUrl": "https://download.example.invalid/content"}, **changes)


class Response:
    def __init__(self, data=None, status=200, content=b""):
        self.data, self.status_code, self.content = data, status, content
    def json(self):
        return deepcopy(self.data)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def iter_content(self, size):
        yield self.content


class Graph:
    def __init__(self):
        self.files, self.calls = {}, []
        self.upload_mode = "success"
        self.download = b"remote"
        self.on_download = lambda: None
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        suffix = unquote(url.split("/drives/drive/", 1)[1])
        if method == "GET" and suffix.endswith("/children"):
            return Response({"value": list(self.files.values())})
        if method == "GET":
            name = suffix.split(":/", 1)[1]
            return Response(self.files.get(name), 200 if name in self.files else 404)
        self.target = kwargs["json"]["item"]["name"]
        assert kwargs["json"]["item"]["@microsoft.graph.conflictBehavior"] == "fail"
        return Response({"uploadUrl": "https://upload.example.invalid/private-session"})
    def put(self, url, **kwargs):
        self.calls.append(("PUT", url, kwargs))
        if self.upload_mode == "timeout":
            raise OSError("secret upload address")
        if self.upload_mode == "collision":
            self.files[self.target] = item(self.target, b"external")
            return Response({}, 409)
        if self.upload_mode == "pending":
            return Response({}, 202)
        self.files[self.target] = item(self.target, kwargs["data"])
        result = deepcopy(self.files[self.target])
        if self.upload_mode == "wrong-result":
            result["name"] = "different.txt"
        return Response(result, 201)
    def get(self, url, **kwargs):
        self.calls.append(("DOWNLOAD", url, kwargs))
        self.on_download()
        return Response(content=self.download)


class OneDriveTransferTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local_root = self.root / "local"
        self.local_root.mkdir()
        self.local = LocalStorageProvider(str(self.local_root), "Local")
        self.graph = Graph()
        self.renewals = 0
        def token():
            self.renewals += 1
            return "secret-token"
        self.cloud = OneDriveProvider("drive", "root", "Test", token, self.graph)
        self.history = SyncHistoryService(JsonSyncHistoryStore(self.root / "history" / "runs"),
            lock_factory=lambda: SyncHistoryLock(self.root / "history" / "sync.lock"))
        self.service = SyncService(self.local, self.cloud, history_service=self.history)

    def preview(self, direction=SyncDirection.LOCAL_TO_SERVER):
        return self.service.create_preview(self.service.compare(), direction)

    def run_job(self, preview):
        job = self.service.create_job(preview)
        worker = self.service.start_job(job, preview)
        worker.join(5)
        self.assertFalse(worker.is_alive())
        return job, self.history.get_record(job.history_run_id)

    def test_compare_preview_confirmed_upload_and_durable_history(self):
        (self.local_root / "new.txt").write_bytes(b"new")
        preview = self.preview()
        self.assertEqual(preview.total_files, 1)
        self.assertFalse(any(call[0] != "GET" for call in self.graph.calls))
        job, history = self.run_job(preview)
        self.assertEqual(job.copied_files, 1)
        self.assertEqual(history.counts.copied, 1)
        self.assertGreater(self.renewals, 1)
        upload = next(call for call in self.graph.calls if call[0] == "PUT")
        self.assertNotIn("Authorization", upload[2]["headers"])
        self.assertFalse(upload[2]["allow_redirects"])
        self.assertNotIn("secret-token", str(history))

    def test_final_collision_preserves_external_file_and_records_skip_without_retry(self):
        (self.local_root / "new.txt").write_bytes(b"new")
        preview = self.preview()
        self.graph.upload_mode = "collision"
        job, history = self.run_job(preview)
        self.assertEqual(job.skipped_files, 1)
        self.assertEqual(history.files[0].reason_code, SyncReasonCode.DESTINATION_APPEARED)
        self.assertEqual(self.graph.files["new.txt"]["size"], len(b"external"))
        self.assertEqual(sum(call[0] == "PUT" for call in self.graph.calls), 1)

    def test_unknown_upload_is_not_success_and_never_retried(self):
        for mode in ("timeout", "pending", "wrong-result"):
            with self.subTest(mode=mode):
                self.graph.files.clear()
                self.graph.calls.clear()
                (self.local_root / "new.txt").write_bytes(b"new")
                preview = self.preview()
                self.graph.upload_mode = mode
                job, history = self.run_job(preview)
                self.assertEqual(job.copied_files, 0)
                self.assertEqual(history.files[0].reason_code, SyncReasonCode.TRANSFER_OUTCOME_UNKNOWN)
                self.assertEqual(sum(call[0] == "PUT" for call in self.graph.calls), 1)
                self.assertNotIn("private-session", str(history))

    def test_download_to_local_new_file_uses_existing_history_flow(self):
        for name, content in (("remote.txt", b"remote"), ("empty.txt", b"")):
            with self.subTest(name=name):
                self.graph.files.clear()
                self.graph.files[name] = item(name, content)
                self.graph.download = content
                job, history = self.run_job(self.preview(SyncDirection.SERVER_TO_LOCAL))
                self.assertEqual(job.copied_files, 1)
                self.assertEqual((self.local_root / name).read_bytes(), content)
                self.assertEqual(history.counts.copied, 1)

    def test_source_changed_during_download_does_not_publish(self):
        self.graph.files["remote.txt"] = item("remote.txt")
        preview = self.preview(SyncDirection.SERVER_TO_LOCAL)
        self.graph.on_download = lambda: self.graph.files["remote.txt"].update(eTag="v2")
        job, history = self.run_job(preview)
        self.assertEqual(job.skipped_files, 1)
        self.assertFalse((self.local_root / "remote.txt").exists())
        self.assertEqual(history.files[0].reason_code, SyncReasonCode.SOURCE_CHANGED)

    def test_overwrite_excluded_and_forged_preview_blocked_in_both_directions(self):
        (self.local_root / "new.txt").write_bytes(b"new")
        preview = self.preview()
        forged = replace(preview, items=(replace(preview.items[0], overwrite=True),))
        job, history = self.run_job(forged)
        self.assertEqual(job.skipped_files, 1)
        self.assertFalse(any(call[0] == "POST" for call in self.graph.calls))
        self.graph.files["new.txt"] = item("new.txt")
        self.assertEqual(self.preview().total_files, 0)
        self.assertEqual(self.preview(SyncDirection.SERVER_TO_LOCAL).total_files, 0)
        job = self.service.create_job(forged)
        SyncJobRunner(self.cloud, self.local).run(job, forged)
        self.assertEqual(job.skipped_files, 1)
        self.assertEqual((self.local_root / "new.txt").read_bytes(), b"new")

    def test_missing_parent_and_empty_upload_are_excluded_explicitly(self):
        (self.local_root / "sub").mkdir()
        (self.local_root / "sub" / "new.txt").write_bytes(b"new")
        (self.local_root / "empty.txt").write_bytes(b"")
        preview = self.preview()
        self.assertEqual(preview.total_files, 0)
        self.assertIn("2 file(s) excluded", preview.warnings[0])

    def test_fresh_metadata_lookup_detects_remote_change_after_scan(self):
        self.graph.files["remote.txt"] = item("remote.txt")
        record = self.cloud.scan()["remote.txt"]
        self.graph.files["remote.txt"]["eTag"] = "v2"
        self.assertNotEqual(self.cloud.get_record("remote.txt").metadata, record.metadata)

    def test_unsafe_paths_fail_before_network(self):
        for path in ("../file", "/file", "a//b", "a\\b", "file:stream", "CON.txt", "x. "):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.cloud.get_record(path)
        self.assertEqual(self.graph.calls, [])

    def test_changed_source_before_upload_and_truncated_download_do_not_write_destination(self):
        (self.local_root / "new.txt").write_bytes(b"new")
        preview = self.preview()
        (self.local_root / "new.txt").write_bytes(b"changed source")
        job, history = self.run_job(preview)
        self.assertEqual(job.skipped_files, 1)
        self.assertFalse(any(call[0] == "POST" for call in self.graph.calls))
        self.graph.files["remote.txt"] = item("remote.txt")
        self.graph.download = b"bad"
        job, history = self.run_job(self.preview(SyncDirection.SERVER_TO_LOCAL))
        self.assertEqual(job.failed_files, 1)
        self.assertFalse((self.local_root / "remote.txt").exists())

    def test_duplicate_names_shortcuts_and_foreign_paging_fail_closed(self):
        from unittest.mock import patch
        for page in (
            {"value": [item("a.txt"), item("A.txt")]},
            {"value": [dict(item("a.txt"), remoteItem={})]},
            {"value": [], "@odata.nextLink": "https://evil.invalid/token"},
        ):
            with self.subTest(page=page):
                with patch.object(self.graph, "request", return_value=Response(page)):
                    with self.assertRaises(TransferFailed):
                        self.cloud.scan()
                self.assertEqual(self.cloud._records, {})

    def test_upload_chunk_ranges_and_final_result_validation(self):
        from unittest.mock import patch
        path = self.root / "large"
        size = 10 * 1024 * 1024 + 1
        with path.open("wb") as output:
            output.truncate(size)
        final = item("large", b"x")
        final["size"] = size
        with patch.object(self.graph, "put", side_effect=[
            Response({"nextExpectedRanges": [f"{size-1}-"]}, 202), Response(final, 201)]) as put:
            self.cloud._upload("https://upload.example.invalid/session", path, size, "large", "root")
        self.assertEqual(put.call_count, 2)
        self.assertEqual(put.call_args_list[1].kwargs["headers"]["Content-Range"], f"bytes {size-1}-{size-1}/{size}")
