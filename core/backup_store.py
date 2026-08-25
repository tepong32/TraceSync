from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from models.backup_record import BackupRecord


DEFAULT_BACKUP_RETENTION = 500
DEFAULT_PER_FILE_BACKUP_RETENTION = 2
DEFAULT_BACKUP_SIZE_LIMIT_BYTES = 5 * 1024**3


@dataclass(frozen=True, slots=True)
class StoredBackup:
    record: BackupRecord
    content_path: Path


class JsonBackupStore:
    """Stores independently recoverable backup content and metadata."""

    def __init__(
        self,
        backup_directory: Path | None = None,
        *,
        retention_limit: int = DEFAULT_BACKUP_RETENTION,
        per_file_retention_limit: int = DEFAULT_PER_FILE_BACKUP_RETENTION,
        size_limit_bytes: int = DEFAULT_BACKUP_SIZE_LIMIT_BYTES,
    ) -> None:
        if retention_limit < 1:
            raise ValueError("Backup retention must keep at least one file.")
        if per_file_retention_limit < 1:
            raise ValueError("Per-file backup retention must keep at least one version.")
        if size_limit_bytes < 1:
            raise ValueError("Backup storage limit must be at least one byte.")
        self.backup_directory = backup_directory or default_backup_directory()
        self.records_directory = self.backup_directory / "records"
        self.files_directory = self.backup_directory / "files"
        self.retention_limit = retention_limit
        self.per_file_retention_limit = per_file_retention_limit
        self.size_limit_bytes = size_limit_bytes

    def create(self, record: BackupRecord, source_path: Path) -> None:
        record_path = self._record_path(record.backup_id)
        content_path = self._content_path(record.backup_id)
        if record_path.exists() or content_path.exists():
            raise FileExistsError(f"Backup already exists: {record.backup_id}")
        if not source_path.is_file():
            raise FileNotFoundError("The destination file is no longer available for backup.")

        source_stat = source_path.stat()
        if (
            source_stat.st_size != record.original_size
            or source_stat.st_mtime != record.original_modified_time
        ):
            raise OSError("The destination file changed before it could be backed up.")

        self.records_directory.mkdir(parents=True, exist_ok=True)
        self.files_directory.mkdir(parents=True, exist_ok=True)
        temporary_content: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{record.backup_id}.",
                suffix=".tmp",
                dir=self.files_directory,
                delete=False,
            ) as temporary_file:
                temporary_content = Path(temporary_file.name)
            shutil.copy2(source_path, temporary_content)
            _flush_file(temporary_content)
            final_source_stat = source_path.stat()
            copied_stat = temporary_content.stat()
            if (
                final_source_stat.st_size != record.original_size
                or final_source_stat.st_mtime != record.original_modified_time
                or copied_stat.st_size != record.original_size
                or copied_stat.st_mtime != record.original_modified_time
            ):
                raise OSError("The backup copy could not be verified.")
            os.replace(temporary_content, content_path)
            temporary_content = None
            self._write_record_atomic(record, record_path)
        except Exception:
            if temporary_content is not None:
                temporary_content.unlink(missing_ok=True)
            content_path.unlink(missing_ok=True)
            record_path.unlink(missing_ok=True)
            raise

    def get(self, backup_id: str) -> StoredBackup | None:
        record_path = self._record_path(backup_id)
        content_path = self._content_path(backup_id)
        if not record_path.is_file() or not content_path.is_file():
            return None
        record = self._read_record(record_path)
        if UUID(record.backup_id) != UUID(backup_id):
            raise ValueError("Backup record identity does not match its filename.")
        content_stat = content_path.stat()
        if (
            content_stat.st_size != record.original_size
            or content_stat.st_mtime != record.original_modified_time
        ):
            raise OSError("The backup file is incomplete or has changed.")
        return StoredBackup(record=record, content_path=content_path)

    def latest_for_recovery_group(self, recovery_group_id: str) -> StoredBackup | None:
        """Return the newest valid restore point in one history-linked chain."""
        normalized_group_id = UUID(recovery_group_id)
        matches = [
            stored
            for stored in self._load_valid_backups()
            if UUID(stored.record.recovery_group_id or stored.record.backup_id)
            == normalized_group_id
        ]
        return matches[0] if matches else None

    def recovery_groups_for_run(self, run_id: str) -> dict[str, str]:
        """Discover backups even when terminal history finalization was interrupted."""
        normalized_run_id = UUID(run_id)
        groups_by_path: dict[str, str] = {}
        for stored in self._load_valid_backups():
            if UUID(stored.record.run_id) != normalized_run_id:
                continue
            groups_by_path.setdefault(
                stored.record.relative_path,
                stored.record.recovery_group_id or stored.record.backup_id,
            )
        return groups_by_path

    def apply_retention(self, protected_backup_id: str | None = None) -> int:
        protected = UUID(protected_backup_id) if protected_backup_id else None
        backups = self._load_valid_backups()
        protected_backup = next(
            (
                stored
                for stored in backups
                if UUID(stored.record.backup_id) == protected
            ),
            None,
        )
        kept_backups: list[StoredBackup] = []
        versions_per_file: dict[tuple[str, str, str], int] = {}
        if protected_backup is not None:
            kept_backups.append(protected_backup)
            protected_identity = self._backup_identity(protected_backup.record)
            versions_per_file[protected_identity] = 1

        for stored in backups:
            backup_uuid = UUID(stored.record.backup_id)
            if backup_uuid == protected:
                continue
            if len(kept_backups) >= self.retention_limit:
                break
            identity = self._backup_identity(stored.record)
            if versions_per_file.get(identity, 0) >= self.per_file_retention_limit:
                continue
            kept_backups.append(stored)
            versions_per_file[identity] = versions_per_file.get(identity, 0) + 1

        kept_ids = {UUID(stored.record.backup_id) for stored in kept_backups}
        total_size = sum(stored.record.original_size for stored in kept_backups)
        for stored in reversed(kept_backups):
            if total_size <= self.size_limit_bytes:
                break
            backup_uuid = UUID(stored.record.backup_id)
            if backup_uuid == protected:
                continue
            kept_ids.remove(backup_uuid)
            total_size -= stored.record.original_size

        deleted = 0
        for stored in backups:
            backup_uuid = UUID(stored.record.backup_id)
            if backup_uuid in kept_ids:
                continue
            stored.content_path.unlink(missing_ok=True)
            self._record_path(stored.record.backup_id).unlink(missing_ok=True)
            deleted += 1
        return deleted

    @staticmethod
    def _backup_identity(record: BackupRecord) -> tuple[str, str, str]:
        """Identify one destination file independently of display-name changes."""
        return (
            record.destination.provider_type.casefold(),
            record.destination.locator.replace("\\", "/").rstrip("/").casefold(),
            record.relative_path.replace("\\", "/").casefold(),
        )

    def _load_valid_backups(self) -> list[StoredBackup]:
        if not self.records_directory.is_dir():
            return []
        backups: list[StoredBackup] = []
        for record_path in self.records_directory.glob("*.json"):
            try:
                filename_id = UUID(record_path.stem)
                record = self._read_record(record_path)
                if filename_id != UUID(record.backup_id):
                    continue
                content_path = self._content_path(record.backup_id)
                content_stat = content_path.stat()
                if (
                    not content_path.is_file()
                    or content_stat.st_size != record.original_size
                    or content_stat.st_mtime != record.original_modified_time
                ):
                    continue
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue
            backups.append(StoredBackup(record, content_path))
        backups.sort(key=lambda item: item.record.created_at_utc, reverse=True)
        return backups

    def _record_path(self, backup_id: str) -> Path:
        return self.records_directory / f"{UUID(backup_id)}.json"

    def _content_path(self, backup_id: str) -> Path:
        return self.files_directory / f"{UUID(backup_id)}.bak"

    @staticmethod
    def _read_record(path: Path) -> BackupRecord:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Backup record must be a JSON object.")
        return BackupRecord.from_dict(data)

    def _write_record_atomic(self, record: BackupRecord, target: Path) -> None:
        payload = json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{record.backup_id}.",
                suffix=".tmp",
                dir=self.records_directory,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, target)
        except Exception:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise


def default_backup_directory() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return base / "TraceSync" / "backups"


def _flush_file(path: Path) -> None:
    with path.open("r+b") as backup_file:
        os.fsync(backup_file.fileno())
