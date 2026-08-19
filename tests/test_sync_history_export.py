import csv
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from core.sync_history_service import SyncHistoryService
from core.sync_history_store import JsonSyncHistoryStore
from models.sync_direction import SyncDirection
from models.sync_history import (
    StorageEndpointSnapshot,
    SyncFileOutcome,
    SyncFileOutcomeRecord,
    SyncReasonCode,
    SyncRunCounts,
    SyncRunOutcome,
    SyncRunRecord,
)


def make_export_record(run_id: str, dangerous: bool = False) -> SyncRunRecord:
    prefix = "  =" if dangerous else ""
    files = (
        SyncFileOutcomeRecord(
            relative_path=f"{prefix}quarterly.xlsx",
            operation="copy",
            overwrite=False,
            outcome=SyncFileOutcome.COPIED,
        ),
        SyncFileOutcomeRecord(
            relative_path="review.docx",
            operation="overwrite",
            overwrite=True,
            outcome=SyncFileOutcome.SKIPPED,
            reason_code=SyncReasonCode.DESTINATION_CHANGED,
            message="@SUM(1+1)" if dangerous else "Destination changed.",
        ),
    )
    return SyncRunRecord(
        run_id=run_id,
        application_version="0.8.5",
        outcome=SyncRunOutcome.COMPLETED_WITH_ISSUES,
        started_at_utc="2026-08-19T01:02:03.000Z",
        finished_at_utc="2026-08-19T01:02:04.000Z",
        duration_ms=1000,
        direction=SyncDirection.LOCAL_TO_SERVER,
        source=StorageEndpointSnapshot(
            "local",
            "+Source" if dangerous else "Source",
            "C:/source",
        ),
        destination=StorageEndpointSnapshot("local", "Destination", "D:/destination"),
        counts=SyncRunCounts(
            planned=2,
            planned_overwrites=1,
            copied=1,
            skipped=1,
        ),
        files=files,
    )


class SyncHistoryExportTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.store = JsonSyncHistoryStore(self.root / "history" / "runs")
        self.service = SyncHistoryService(self.store)

    def test_export_contains_one_row_per_file_for_only_selected_run(self):
        selected = make_export_record(str(uuid4()))
        other = make_export_record(str(uuid4()))
        self.store.create(selected)
        self.store.create(other)
        destination = self.root / "selected.csv"

        self.service.export_run(selected.run_id, destination)

        with destination.open(encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["run_id"] for row in rows}, {selected.run_id})
        self.assertEqual(
            {row["relative_path"] for row in rows},
            {"quarterly.xlsx", "review.docx"},
        )

    def test_export_hardens_formula_like_fields_after_leading_whitespace(self):
        record = make_export_record(str(uuid4()), dangerous=True)
        self.store.create(record)
        destination = self.root / "safe.csv"

        self.service.export_run(record.run_id, destination)

        with destination.open(encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))
        self.assertEqual(rows[0]["source_display_name"], "'+Source")
        self.assertEqual(rows[0]["relative_path"], "'  =quarterly.xlsx")
        self.assertEqual(rows[1]["message"], "'@SUM(1+1)")

    def test_export_missing_run_does_not_create_a_file(self):
        destination = self.root / "missing.csv"

        with self.assertRaises(ValueError):
            self.service.export_run(str(uuid4()), destination)

        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
