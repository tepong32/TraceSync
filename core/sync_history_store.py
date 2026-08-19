from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from models.sync_history import SyncRunRecord


DEFAULT_HISTORY_RETENTION = 500


@dataclass(frozen=True, slots=True)
class HistoryLoadResult:
    records: tuple[SyncRunRecord, ...]
    unreadable_files: tuple[Path, ...] = ()


@dataclass(frozen=True, slots=True)
class _ValidatedHistoryFile:
    record: SyncRunRecord
    source_path: Path


class SyncHistoryStore(Protocol):
    def create(self, record: SyncRunRecord) -> None: ...

    def replace(self, record: SyncRunRecord) -> None: ...

    def get(self, run_id: str) -> SyncRunRecord | None: ...

    def list_records(self, limit: int | None = None) -> HistoryLoadResult: ...

    def apply_retention(self, protected_run_id: str | None = None) -> int: ...

    def clear(self) -> int: ...


class JsonSyncHistoryStore:
    """Atomic, independently recoverable JSON storage for synchronization runs."""

    def __init__(
        self,
        history_directory: Path | None = None,
        *,
        retention_limit: int = DEFAULT_HISTORY_RETENTION,
    ) -> None:
        if retention_limit < 1:
            raise ValueError("History retention must keep at least one run.")
        self.history_directory = history_directory or default_history_directory()
        self.retention_limit = retention_limit

    def create(self, record: SyncRunRecord) -> None:
        target = self._record_path(record.run_id)
        if target.exists():
            raise FileExistsError(f"History record already exists: {record.run_id}")
        self._write_atomic(record, target)

    def replace(self, record: SyncRunRecord) -> None:
        target = self._record_path(record.run_id)
        if not target.is_file():
            raise FileNotFoundError(f"History record does not exist: {record.run_id}")
        self._write_atomic(record, target)

    def get(self, run_id: str) -> SyncRunRecord | None:
        path = self._record_path(run_id)
        if not path.is_file():
            return None
        return self._read_record(path)

    def list_records(self, limit: int | None = None) -> HistoryLoadResult:
        if limit is not None and limit < 0:
            raise ValueError("History list limit cannot be negative.")
        validated_files, unreadable = self._load_validated_files()
        if limit is not None:
            validated_files = validated_files[:limit]
        return HistoryLoadResult(
            records=tuple(item.record for item in validated_files),
            unreadable_files=unreadable,
        )

    def apply_retention(self, protected_run_id: str | None = None) -> int:
        validated_files, _unreadable = self._load_validated_files()
        protected_uuid = UUID(protected_run_id) if protected_run_id is not None else None
        protected = [
            item
            for item in validated_files
            if protected_uuid is not None and UUID(item.record.run_id) == protected_uuid
        ]
        candidates = [item for item in validated_files if item not in protected]
        keep_count = self.retention_limit - len(protected)
        kept_paths = {
            item.source_path
            for item in candidates[:max(0, keep_count)]
        }
        kept_paths.update(item.source_path for item in protected)

        deleted = 0
        for item in validated_files:
            if item.source_path in kept_paths:
                continue
            try:
                item.source_path.unlink()
                deleted += 1
            except FileNotFoundError:
                continue
        return deleted

    def clear(self) -> int:
        if not self.history_directory.is_dir():
            return 0
        deleted = 0
        for path in self.history_directory.glob("*.json"):
            try:
                path.unlink()
                deleted += 1
            except FileNotFoundError:
                continue
        for path in self.history_directory.glob(".*.tmp"):
            try:
                path.unlink()
            except FileNotFoundError:
                continue
        return deleted

    def _record_path(self, run_id: str) -> Path:
        normalized_run_id = str(UUID(run_id))
        return self.history_directory / f"{normalized_run_id}.json"

    @staticmethod
    def _read_record(path: Path) -> SyncRunRecord:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("History record must be a JSON object.")
        return SyncRunRecord.from_dict(data)

    def _load_validated_files(
        self,
    ) -> tuple[list[_ValidatedHistoryFile], tuple[Path, ...]]:
        if not self.history_directory.is_dir():
            return [], ()

        files_by_run_id: dict[UUID, list[_ValidatedHistoryFile]] = {}
        unreadable: list[Path] = []
        for path in self.history_directory.glob("*.json"):
            try:
                filename_run_id = UUID(path.stem)
                record = self._read_record(path)
                payload_run_id = UUID(record.run_id)
                if filename_run_id != payload_run_id:
                    raise ValueError("History filename does not match its run ID.")
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                unreadable.append(path)
                continue
            files_by_run_id.setdefault(payload_run_id, []).append(
                _ValidatedHistoryFile(record=record, source_path=path)
            )

        validated_files: list[_ValidatedHistoryFile] = []
        for matching_files in files_by_run_id.values():
            if len(matching_files) > 1:
                unreadable.extend(item.source_path for item in matching_files)
                continue
            validated_files.extend(matching_files)

        validated_files.sort(
            key=lambda item: item.record.started_at_utc,
            reverse=True,
        )
        return validated_files, tuple(sorted(unreadable))

    def _write_atomic(self, record: SyncRunRecord, target: Path) -> None:
        self.history_directory.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{record.run_id}.",
                suffix=".tmp",
                dir=self.history_directory,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, target)
        except Exception:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except FileNotFoundError:
                    pass
            raise


def default_history_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "TraceSync" / "history" / "runs"
