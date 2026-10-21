import os
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy
from unittest.mock import Mock

from core.onedrive_timestamps import format_modified_time, parse_modified_time
from core.onedrive_provider import OneDriveProvider
from models.compare_status import CompareStatus
from tests import test_onedrive_transfer as transfer_fixture
from tests.test_onedrive_transfer import Graph, Response


class TimestampTests(unittest.TestCase):
    def test_rfc3339_preserves_seventh_digit_and_time_zone(self):
        precise = parse_modified_time("2026-10-21T00:00:00.1234567Z")
        self.assertNotEqual(precise, parse_modified_time("2026-10-21T00:00:00.1234560Z"))
        self.assertEqual(precise, parse_modified_time("2026-10-21T01:00:00.1234567+01:00"))
        self.assertEqual(parse_modified_time(format_modified_time(precise)), precise)
        for value in ("2026-10-21T00:00:00", "2026-10-21T00:00:00.00000001Z", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_modified_time(value)
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                format_modified_time(value)

    @unittest.skipUnless(os.name == "nt", "Native Windows file timestamps")
    def test_native_file_stat_round_trips_at_ntfs_precision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic"
            path.write_bytes(b"synthetic")
            for fraction in range(0, 10000, 137):
                stamp = 1792540800000000000 + fraction * 100
                os.utime(path, ns=(stamp, stamp))
                observed = path.stat().st_mtime
                self.assertEqual(parse_modified_time(format_modified_time(observed)), observed)

    def test_client_time_takes_precedence_but_etag_remains_change_identity(self):
        from tests.test_onedrive_transfer import item
        provider = OneDriveProvider("drive", "root", "Test", Mock(), Mock())
        data = item("new.txt")
        data["fileSystemInfo"] = {"lastModifiedDateTime": "2026-10-21T00:00:00.1234567Z"}
        record = provider._record(data, "new.txt")
        self.assertEqual(record.metadata.version_id, "v1")
        self.assertEqual(record.modified_time, parse_modified_time(data["fileSystemInfo"]["lastModifiedDateTime"]))


class TimestampGraph(Graph):
    def __init__(self):
        super().__init__()
        self.properties = {}
        self.metadata_mode = "success"
        self.patch_calls = []

    def request(self, method, url, **kwargs):
        if method == "PATCH":
            self.calls.append((method, url, kwargs))
            self.patch_calls.append((url, deepcopy(kwargs)))
            current = next(value for value in self.files.values() if url.endswith("/" + value["id"]))
            if self.metadata_mode == "timeout":
                raise OSError("synthetic private URL")
            if self.metadata_mode in ("403", "412"):
                return Response({}, int(self.metadata_mode))
            if self.metadata_mode == "changed":
                current.update(eTag="external", size=8)
            if kwargs["headers"]["If-Match"] != current["eTag"]:
                return Response({}, 412)
            current["fileSystemInfo"] = deepcopy(kwargs["json"]["fileSystemInfo"])
            current["eTag"] = "timestamp-updated"
            result = deepcopy(current)
            if self.metadata_mode == "malformed":
                return Response(["invalid"])
            if self.metadata_mode == "wrong-id":
                result["id"] = "other"
            return Response(result)
        result = super().request(method, url, **kwargs)
        if method == "POST" and "createUploadSession" in url:
            self.properties = deepcopy(kwargs["json"]["item"])
        if method == "PUT" and self.metadata_mode == "missing-version":
            result.data.pop("eTag", None)
        return result

    def put(self, url, **kwargs):
        result = super().put(url, **kwargs)
        if result.status_code == 201 and self.upload_mode == "success":
            self.files[self.target]["fileSystemInfo"] = deepcopy(self.properties.get("fileSystemInfo", {}))
            result.data = deepcopy(self.files[self.target])
        return result


class UploadTimestampTests(unittest.TestCase):
    def setUp(self):
        # Reuse the established real local/history fixture without inheriting and
        # duplicating all its test methods in this module's discovery.
        self.fixture = transfer_fixture.OneDriveTransferTests("test_locked_upload_snapshot_does_not_turn_a_committed_copy_into_failure")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.graph = TimestampGraph()
        self.fixture.cloud._session = self.graph

    def test_nonempty_session_carries_reviewed_time_and_next_compare_is_same(self):
        path = self.fixture.local_root / "new.txt"
        path.write_bytes(b"synthetic")
        os.utime(path, ns=(1792540800123456700, 1792540800123456700))
        observed = path.stat().st_mtime
        job, history = self.fixture.run_job(self.fixture.preview())
        self.assertEqual(job.copied_files, 1)
        self.assertEqual(history.counts.copied, 1)
        self.assertEqual(parse_modified_time(self.graph.properties["fileSystemInfo"]["lastModifiedDateTime"]), observed)
        self.assertEqual(self.fixture.service.compare()[0].status, CompareStatus.SAME)
        self.assertEqual(self.graph.patch_calls, [])

    def test_empty_create_updates_only_confirmed_id_and_version_then_compares_same(self):
        path = self.fixture.local_root / "empty.txt"
        path.write_bytes(b"")
        job, history = self.fixture.run_job(self.fixture.preview())
        self.assertEqual((job.copied_files, history.counts.copied), (1, 1))
        self.assertEqual(len(self.graph.patch_calls), 1)
        url, request = self.graph.patch_calls[0]
        self.assertTrue(url.endswith("/items/id-empty.txt"))
        self.assertEqual(request["headers"]["If-Match"], "v1")
        self.assertEqual(set(request["json"]), {"fileSystemInfo"})
        self.assertEqual(self.fixture.service.compare()[0].status, CompareStatus.SAME)

    def test_metadata_failure_keeps_confirmed_copy_and_honest_note_without_retry(self):
        for mode in ("missing-version", "403", "412", "timeout", "malformed", "wrong-id", "changed"):
            with self.subTest(mode=mode):
                self.graph.files.clear()
                self.graph.patch_calls.clear()
                self.graph.metadata_mode = mode
                path = self.fixture.local_root / "empty.txt"
                path.write_bytes(b"")
                job, history = self.fixture.run_job(self.fixture.preview())
                self.assertEqual((job.copied_files, job.failed_files), (1, 0))
                self.assertEqual(history.counts.copied, 1)
                self.assertIn("modification time was not confirmed", history.files[0].message)
                self.assertIn("No retry", history.files[0].message)
                self.assertEqual(len(self.graph.patch_calls), 0 if mode == "missing-version" else 1)
                if mode == "changed":
                    self.assertEqual(self.graph.files["empty.txt"]["eTag"], "external")
                    self.assertEqual(self.graph.files["empty.txt"]["size"], 8)
