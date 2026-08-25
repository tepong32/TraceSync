from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from models.sync_history import StorageEndpointSnapshot


BACKUP_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class BackupRecord:
    """Durable metadata for one destination file saved before replacement."""

    backup_id: str
    run_id: str
    created_at_utc: str
    relative_path: str
    destination: StorageEndpointSnapshot
    original_size: int
    original_modified_time: float
    recovery_group_id: str | None = None
    schema_version: int = BACKUP_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != BACKUP_SCHEMA_VERSION:
            raise ValueError(f"Unsupported backup schema version: {self.schema_version}")
        UUID(self.backup_id)
        UUID(self.run_id)
        if not self.relative_path:
            raise ValueError("Backup relative path is required.")
        if self.original_size < 0:
            raise ValueError("Backup size cannot be negative.")
        if self.recovery_group_id is not None:
            UUID(self.recovery_group_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "backup_id": self.backup_id,
            "run_id": self.run_id,
            "created_at_utc": self.created_at_utc,
            "relative_path": self.relative_path,
            "destination": self.destination.to_dict(),
            "original_size": self.original_size,
            "original_modified_time": self.original_modified_time,
            "recovery_group_id": self.recovery_group_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupRecord":
        return cls(
            schema_version=int(data.get("schema_version", 0)),
            backup_id=str(data["backup_id"]),
            run_id=str(data["run_id"]),
            created_at_utc=str(data["created_at_utc"]),
            relative_path=str(data["relative_path"]),
            destination=StorageEndpointSnapshot.from_dict(data["destination"]),
            original_size=int(data["original_size"]),
            original_modified_time=float(data["original_modified_time"]),
            recovery_group_id=(
                str(data["recovery_group_id"])
                if data.get("recovery_group_id") is not None
                else None
            ),
        )
