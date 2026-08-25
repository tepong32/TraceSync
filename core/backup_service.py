from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from core.backup_store import JsonBackupStore
from core.local_storage_provider import LocalStorageProvider
from core.storage_provider import StorageProvider
from models.backup_record import BackupRecord


class BackupCreationError(RuntimeError):
    """Raised when a required pre-overwrite backup cannot be made."""


@dataclass(frozen=True, slots=True)
class RestoreResult:
    restored_backup_id: str
    safety_backup_id: str | None


class BackupService:
    """Creates required overwrite backups and restores them on request."""

    def __init__(
        self,
        store: JsonBackupStore | None = None,
        *,
        now_provider: Callable[[], datetime] | None = None,
        id_provider: Callable[[], str] | None = None,
    ) -> None:
        self.store = store or JsonBackupStore()
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.id_provider = id_provider or (lambda: str(uuid4()))

    def create_backup(
        self,
        destination_provider: StorageProvider,
        relative_path: str,
        run_id: str,
    ) -> BackupRecord:
        return self._create_backup(
            destination_provider,
            relative_path,
            run_id,
            maintain_retention=True,
        )

    def _create_backup(
        self,
        destination_provider: StorageProvider,
        relative_path: str,
        run_id: str,
        *,
        maintain_retention: bool,
        recovery_group_id: str | None = None,
    ) -> BackupRecord:
        if not isinstance(destination_provider, LocalStorageProvider):
            raise BackupCreationError(
                "This destination provider cannot create a required overwrite backup."
            )
        destination_record = destination_provider.get_record(relative_path)
        if destination_record is None:
            raise BackupCreationError(
                "The destination file is no longer available for backup. Compare again before copying."
            )
        backup_id = self.id_provider()
        record = BackupRecord(
            backup_id=backup_id,
            run_id=run_id,
            created_at_utc=_backup_timestamp(self.now_provider()),
            relative_path=relative_path,
            destination=destination_provider.describe_endpoint(),
            original_size=destination_record.size,
            original_modified_time=destination_record.modified_time,
            recovery_group_id=recovery_group_id or backup_id,
        )
        try:
            self.store.create(record, Path(destination_record.absolute_path))
        except Exception as exc:
            raise BackupCreationError(
                "TraceSync could not safely back up the existing destination file. It was not overwritten."
            ) from exc
        if maintain_retention:
            try:
                self.store.apply_retention(protected_backup_id=record.backup_id)
            except Exception:
                # The required backup is durable. Cleanup failure must not discard it.
                pass
        return record

    def restore(self, backup_id: str) -> RestoreResult:
        direct = self.store.get(backup_id)
        recovery_group_id = (
            direct.record.recovery_group_id if direct is not None else backup_id
        )
        stored = self.store.latest_for_recovery_group(recovery_group_id or backup_id)
        if stored is None:
            raise FileNotFoundError("The selected backup is no longer available.")
        record = stored.record
        if record.destination.provider_type != "local":
            raise NotImplementedError("Restoring this provider type is not supported yet.")

        destination = LocalStorageProvider(
            record.destination.locator,
            record.destination.display_name,
        )
        safety_backup_id: str | None = None
        if destination.get_record(record.relative_path) is not None:
            safety_record = self._create_backup(
                destination,
                record.relative_path,
                record.run_id,
                maintain_retention=False,
                recovery_group_id=record.recovery_group_id or record.backup_id,
            )
            safety_backup_id = safety_record.backup_id
        destination.replace_from_file(stored.content_path, record.relative_path)
        try:
            self.store.apply_retention(protected_backup_id=safety_backup_id or backup_id)
        except Exception:
            pass
        return RestoreResult(record.backup_id, safety_backup_id)

    def backup_ids_for_run(self, run_id: str) -> dict[str, str]:
        try:
            return self.store.recovery_groups_for_run(run_id)
        except (OSError, ValueError):
            # Backup discovery must not prevent otherwise valid history from opening.
            return {}


def _backup_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Backup timestamps must be timezone-aware.")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00",
        "Z",
    )
