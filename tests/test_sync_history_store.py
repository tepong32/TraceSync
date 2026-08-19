import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from core.sync_history_store import JsonSyncHistoryStore, default_history_directory
from models.sync_direction import SyncDirection
from models.sync_history import (
    StorageEndpointSnapshot,
    SyncFileOutcome,
    SyncFileOutcomeRecord,
    SyncRunCounts,
    SyncRunOutcome,
    SyncRunRecord,
    utc_timestamp,
)


def make_record(index: int = 0, *, outcome: SyncRunOutcome = SyncRunOutcome.IN_PROGRESS) -> SyncRunRecord:
    started = datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc) + timedelta(minutes=index)
    file_outcome = SyncFileOutcome.PENDING if outcome is SyncRunOutcome.IN_PROGRESS else SyncFileOutcome.COPIED
    file_record = SyncFileOutcomeRecord(
        relative_path=f"reports/{index}.txt",
        operation="copy",
        overwrite=False,
        outcome=file_outcome,
    )
    terminal = outcome is not SyncRunOutcome.IN_PROGRESS
    return SyncRunRecord(
        run_id=str(uuid4()),
        application_version="0.6.0",
        outcome=outcome,
        started_at_utc=utc_timestamp(started),
        finished_at_utc=utc_timestamp(started + timedelta(seconds=1)) if terminal else None,
        duration_ms=1000 if terminal else None,
        direction=SyncDirection.LOCAL_TO_SERVER,
        source=StorageEndpointSnapshot("local", "Local Folder", "C:/Source"),
        destination=StorageEndpointSnapshot("local", "Server Folder", "D:/Destination"),
        counts=SyncRunCounts(planned=1, planned_overwrites=0, copied=1 if terminal else 0),
        files=(file_record,),
    )


def write_record(path: Path, record: SyncRunRecord) -> None:
    path.write_text(json.dumps(record.to_dict()), encoding="utf-8")


class SyncHistoryModelTests(unittest.TestCase):
    def test_schema_round_trip_tolerates_unknown_optional_fields(self):
        record = make_record()
        serialized = record.to_dict()
        serialized["future_optional_field"] = {"enabled": True}

        self.assertEqual(SyncRunRecord.from_dict(serialized), record)

    def test_counts_must_match_file_outcomes(self):
        record = make_record(outcome=SyncRunOutcome.COMPLETED)

        with self.assertRaises(ValueError):
            replace(record, counts=SyncRunCounts(planned=1, planned_overwrites=0, copied=0))


class JsonSyncHistoryStoreTests(unittest.TestCase):
    def test_default_directory_uses_local_app_data(self):
        with patch.dict("core.sync_history_store.os.environ", {"LOCALAPPDATA": "C:/Users/Test/AppData/Local"}):
            self.assertEqual(
                default_history_directory(),
                Path("C:/Users/Test/AppData/Local/TraceSync/history/runs"),
            )

    def test_create_builds_missing_directory_and_loads_record(self):
        with tempfile.TemporaryDirectory() as workspace:
            history_directory = Path(workspace) / "missing" / "runs"
            store = JsonSyncHistoryStore(history_directory)
            record = make_record()

            store.create(record)

            self.assertEqual(store.get(record.run_id), record)
            self.assertEqual(store.list_records().records, (record,))
            self.assertFalse(tuple(history_directory.glob(".*.tmp")))

    def test_replace_is_atomic_and_preserves_original_on_failure(self):
        with tempfile.TemporaryDirectory() as workspace:
            store = JsonSyncHistoryStore(Path(workspace))
            initial = make_record()
            terminal = replace(
                initial,
                outcome=SyncRunOutcome.COMPLETED,
                finished_at_utc="2026-08-19T08:00:01.000Z",
                duration_ms=1000,
                counts=SyncRunCounts(planned=1, planned_overwrites=0, copied=1),
                files=(replace(initial.files[0], outcome=SyncFileOutcome.COPIED),),
            )
            store.create(initial)

            with patch("core.sync_history_store.os.replace", side_effect=OSError("locked")):
                with self.assertRaises(OSError):
                    store.replace(terminal)

            self.assertEqual(store.get(initial.run_id), initial)
            store.replace(terminal)
            self.assertEqual(store.get(initial.run_id), terminal)

    def test_one_corrupt_record_does_not_hide_valid_records(self):
        with tempfile.TemporaryDirectory() as workspace:
            history_directory = Path(workspace)
            store = JsonSyncHistoryStore(history_directory)
            valid = make_record()
            store.create(valid)
            corrupt = history_directory / "corrupt.json"
            corrupt.write_text("{not-json", encoding="utf-8")

            loaded = store.list_records()

            self.assertEqual(loaded.records, (valid,))
            self.assertEqual(loaded.unreadable_files, (corrupt,))

    def test_filename_payload_mismatch_is_unreadable_and_cannot_target_valid_record(self):
        with tempfile.TemporaryDirectory() as workspace:
            history_directory = Path(workspace)
            store = JsonSyncHistoryStore(history_directory, retention_limit=1)
            protected = make_record(0)
            unrelated = make_record(1)
            store.create(protected)
            store.create(unrelated)
            mismatched_path = history_directory / f"{uuid4()}.json"
            write_record(mismatched_path, protected)

            loaded = store.list_records()

            self.assertEqual(
                {record.run_id for record in loaded.records},
                {protected.run_id, unrelated.run_id},
            )
            self.assertEqual(loaded.unreadable_files, (mismatched_path,))

            self.assertEqual(store.apply_retention(protected.run_id), 1)
            self.assertTrue((history_directory / f"{protected.run_id}.json").exists())
            self.assertTrue(mismatched_path.exists())

    def test_duplicate_run_ids_are_all_unreadable_without_hiding_unrelated_record(self):
        with tempfile.TemporaryDirectory() as workspace:
            history_directory = Path(workspace)
            store = JsonSyncHistoryStore(history_directory)
            duplicate = make_record(0)
            unrelated = make_record(1)
            store.create(duplicate)
            duplicate_path = history_directory / f"{{{duplicate.run_id}}}.json"
            write_record(duplicate_path, duplicate)
            store.create(unrelated)

            loaded = store.list_records()

            canonical_path = history_directory / f"{duplicate.run_id}.json"
            self.assertEqual(loaded.records, (unrelated,))
            self.assertEqual(
                set(loaded.unreadable_files),
                {canonical_path, duplicate_path},
            )
            self.assertTrue(canonical_path.exists())
            self.assertTrue(duplicate_path.exists())

    def test_unsupported_schema_is_reported_as_unreadable(self):
        with tempfile.TemporaryDirectory() as workspace:
            path = Path(workspace) / "future.json"
            payload = make_record().to_dict()
            payload["schema_version"] = 99
            path.write_text(json.dumps(payload), encoding="utf-8")
            store = JsonSyncHistoryStore(Path(workspace))

            loaded = store.list_records()

            self.assertFalse(loaded.records)
            self.assertEqual(loaded.unreadable_files, (path,))

    def test_retention_keeps_newest_records_and_protected_run(self):
        with tempfile.TemporaryDirectory() as workspace:
            store = JsonSyncHistoryStore(Path(workspace), retention_limit=3)
            records = [make_record(index) for index in range(5)]
            for record in records:
                store.create(record)
            corrupt = Path(workspace) / "corrupt.json"
            corrupt.write_text("invalid", encoding="utf-8")

            deleted = store.apply_retention(protected_run_id=records[0].run_id)
            remaining_ids = {record.run_id for record in store.list_records().records}

            self.assertEqual(deleted, 2)
            self.assertEqual(remaining_ids, {records[0].run_id, records[3].run_id, records[4].run_id})
            self.assertTrue(corrupt.exists())

    def test_retention_deletes_exact_validated_paths_and_preserves_invalid_files(self):
        with tempfile.TemporaryDirectory() as workspace:
            history_directory = Path(workspace)
            store = JsonSyncHistoryStore(history_directory, retention_limit=2)
            alternate_old = make_record(0)
            alternate_old_path = history_directory / f"{{{alternate_old.run_id}}}.json"
            write_record(alternate_old_path, alternate_old)
            canonical_old = make_record(1)
            newest = [make_record(2), make_record(3)]
            store.create(canonical_old)
            for record in newest:
                store.create(record)

            mismatched_path = history_directory / f"{uuid4()}.json"
            write_record(mismatched_path, newest[-1])
            duplicate = make_record(4)
            duplicate_canonical_path = history_directory / f"{duplicate.run_id}.json"
            duplicate_alternate_path = history_directory / f"{{{duplicate.run_id}}}.json"
            write_record(duplicate_canonical_path, duplicate)
            write_record(duplicate_alternate_path, duplicate)

            deleted = store.apply_retention()

            self.assertEqual(deleted, 2)
            self.assertFalse(alternate_old_path.exists())
            self.assertFalse((history_directory / f"{canonical_old.run_id}.json").exists())
            self.assertTrue(all((history_directory / f"{record.run_id}.json").exists() for record in newest))
            self.assertTrue(mismatched_path.exists())
            self.assertTrue(duplicate_canonical_path.exists())
            self.assertTrue(duplicate_alternate_path.exists())

            loaded = store.list_records()
            self.assertEqual({record.run_id for record in loaded.records}, {record.run_id for record in newest})
            self.assertEqual(
                set(loaded.unreadable_files),
                {mismatched_path, duplicate_canonical_path, duplicate_alternate_path},
            )

    def test_create_rejects_duplicate_run_id(self):
        with tempfile.TemporaryDirectory() as workspace:
            store = JsonSyncHistoryStore(Path(workspace))
            record = make_record()
            store.create(record)

            with self.assertRaises(FileExistsError):
                store.create(record)

    def test_clear_removes_valid_and_corrupt_json_records(self):
        with tempfile.TemporaryDirectory() as workspace:
            history_directory = Path(workspace)
            store = JsonSyncHistoryStore(history_directory)
            store.create(make_record())
            (history_directory / "corrupt.json").write_text("invalid", encoding="utf-8")

            self.assertEqual(store.clear(), 2)
            self.assertFalse(tuple(history_directory.glob("*.json")))
