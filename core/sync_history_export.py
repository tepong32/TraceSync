from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from models.sync_history import SyncRunRecord


CSV_COLUMNS = (
    "schema_version",
    "run_id",
    "application_version",
    "run_outcome",
    "started_at_utc",
    "finished_at_utc",
    "duration_ms",
    "direction",
    "source_provider_type",
    "source_display_name",
    "source_locator",
    "destination_provider_type",
    "destination_display_name",
    "destination_locator",
    "planned_files",
    "planned_overwrites",
    "copied_files",
    "overwritten_files",
    "skipped_files",
    "failed_files",
    "not_attempted_files",
    "unknown_files",
    "relative_path",
    "operation",
    "overwrite",
    "file_outcome",
    "reason_code",
    "message",
)


def export_sync_run_csv(record: SyncRunRecord, destination: Path) -> None:
    """Atomically export one run with one CSV row per approved file."""
    destination = Path(destination)
    if not destination.parent.is_dir():
        raise FileNotFoundError(f"Export folder does not exist: {destination.parent}")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            writer = csv.DictWriter(temporary_file, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for file_outcome in record.files:
                writer.writerow(
                    {
                        key: _protect_csv_value(value)
                        for key, value in _file_row(record, file_outcome).items()
                    }
                )
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
        raise


def _file_row(record, file_outcome) -> dict[str, object]:
    counts = record.counts
    return {
        "schema_version": record.schema_version,
        "run_id": record.run_id,
        "application_version": record.application_version,
        "run_outcome": record.outcome.value,
        "started_at_utc": record.started_at_utc,
        "finished_at_utc": record.finished_at_utc or "",
        "duration_ms": record.duration_ms if record.duration_ms is not None else "",
        "direction": record.direction.display_name,
        "source_provider_type": record.source.provider_type,
        "source_display_name": record.source.display_name,
        "source_locator": record.source.locator,
        "destination_provider_type": record.destination.provider_type,
        "destination_display_name": record.destination.display_name,
        "destination_locator": record.destination.locator,
        "planned_files": counts.planned,
        "planned_overwrites": counts.planned_overwrites,
        "copied_files": counts.copied,
        "overwritten_files": counts.overwritten,
        "skipped_files": counts.skipped,
        "failed_files": counts.failed,
        "not_attempted_files": counts.not_attempted,
        "unknown_files": counts.unknown,
        "relative_path": file_outcome.relative_path,
        "operation": file_outcome.operation,
        "overwrite": file_outcome.overwrite,
        "file_outcome": file_outcome.outcome.value,
        "reason_code": file_outcome.reason_code.value if file_outcome.reason_code else "",
        "message": file_outcome.message or "",
    }


def _protect_csv_value(value: object) -> object:
    """Prevent a string cell from being interpreted as a spreadsheet formula."""
    if not isinstance(value, str):
        return value
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value
