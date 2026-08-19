from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from models.sync_direction import SyncDirection


SYNC_HISTORY_SCHEMA_VERSION = 1


class SyncRunOutcome(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_WITH_ISSUES = "completed_with_issues"
    CANCELLED = "cancelled"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    NO_CHANGES = "no_changes"


class SyncFileOutcome(str, Enum):
    PENDING = "pending"
    COPIED = "copied"
    SKIPPED = "skipped"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"
    UNKNOWN = "unknown"


class SyncReasonCode(str, Enum):
    SOURCE_MISSING = "source_missing"
    SOURCE_CHANGED = "source_changed"
    DESTINATION_APPEARED = "destination_appeared"
    DESTINATION_CHANGED = "destination_changed"
    DESTINATION_MISSING = "destination_missing"
    PERMISSION_DENIED = "permission_denied"
    PROVIDER_UNSUPPORTED = "provider_unsupported"
    COPY_ERROR = "copy_error"
    UNEXPECTED_ERROR = "unexpected_error"
    CANCELLED = "cancelled"
    RUN_FAILED = "run_failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class StorageEndpointSnapshot:
    provider_type: str
    display_name: str
    locator: str

    def __post_init__(self) -> None:
        if not self.provider_type.strip():
            raise ValueError("Provider type is required.")
        if not self.display_name.strip():
            raise ValueError("Provider display name is required.")
        if not self.locator.strip():
            raise ValueError("Provider locator is required.")

    def to_dict(self) -> dict[str, str]:
        return {
            "provider_type": self.provider_type,
            "display_name": self.display_name,
            "locator": self.locator,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StorageEndpointSnapshot":
        return cls(
            provider_type=str(data["provider_type"]),
            display_name=str(data["display_name"]),
            locator=str(data["locator"]),
        )


@dataclass(frozen=True, slots=True)
class SyncFileOutcomeRecord:
    relative_path: str
    operation: str
    overwrite: bool
    outcome: SyncFileOutcome
    reason_code: SyncReasonCode | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if not self.relative_path:
            raise ValueError("Relative path is required.")
        if not self.operation:
            raise ValueError("Operation is required.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "operation": self.operation,
            "overwrite": self.overwrite,
            "outcome": self.outcome.value,
            "reason_code": self.reason_code.value if self.reason_code else None,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncFileOutcomeRecord":
        reason_code = data.get("reason_code")
        overwrite = data["overwrite"]
        if not isinstance(overwrite, bool):
            raise TypeError("File overwrite value must be a boolean.")
        return cls(
            relative_path=str(data["relative_path"]),
            operation=str(data["operation"]),
            overwrite=overwrite,
            outcome=SyncFileOutcome(data["outcome"]),
            reason_code=SyncReasonCode(reason_code) if reason_code else None,
            message=str(data["message"]) if data.get("message") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class SyncRunCounts:
    planned: int
    planned_overwrites: int
    copied: int = 0
    overwritten: int = 0
    skipped: int = 0
    failed: int = 0
    not_attempted: int = 0
    unknown: int = 0

    def __post_init__(self) -> None:
        values = (
            self.planned,
            self.planned_overwrites,
            self.copied,
            self.overwritten,
            self.skipped,
            self.failed,
            self.not_attempted,
            self.unknown,
        )
        if any(value < 0 for value in values):
            raise ValueError("Synchronization counts cannot be negative.")

    @property
    def issue_count(self) -> int:
        return self.skipped + self.failed + self.not_attempted + self.unknown

    def to_dict(self) -> dict[str, int]:
        return {
            "planned": self.planned,
            "planned_overwrites": self.planned_overwrites,
            "copied": self.copied,
            "overwritten": self.overwritten,
            "skipped": self.skipped,
            "failed": self.failed,
            "not_attempted": self.not_attempted,
            "unknown": self.unknown,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncRunCounts":
        return cls(
            planned=int(data["planned"]),
            planned_overwrites=int(data["planned_overwrites"]),
            copied=int(data.get("copied", 0)),
            overwritten=int(data.get("overwritten", 0)),
            skipped=int(data.get("skipped", 0)),
            failed=int(data.get("failed", 0)),
            not_attempted=int(data.get("not_attempted", 0)),
            unknown=int(data.get("unknown", 0)),
        )


@dataclass(frozen=True, slots=True)
class SyncRunRecord:
    run_id: str
    application_version: str
    outcome: SyncRunOutcome
    started_at_utc: str
    finished_at_utc: str | None
    duration_ms: int | None
    direction: SyncDirection
    source: StorageEndpointSnapshot
    destination: StorageEndpointSnapshot
    counts: SyncRunCounts
    files: tuple[SyncFileOutcomeRecord, ...]
    schema_version: int = SYNC_HISTORY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != SYNC_HISTORY_SCHEMA_VERSION:
            raise ValueError(f"Unsupported history schema version: {self.schema_version}")
        UUID(self.run_id)
        if not self.application_version.strip():
            raise ValueError("Application version is required.")
        _validate_utc_timestamp(self.started_at_utc)
        if self.finished_at_utc is not None:
            _validate_utc_timestamp(self.finished_at_utc)
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("Duration cannot be negative.")
        if self.counts.planned != len(self.files):
            raise ValueError("Planned count must match the file outcome count.")
        if self.counts.planned_overwrites != sum(item.overwrite for item in self.files):
            raise ValueError("Planned overwrite count must match the file records.")
        if len({item.relative_path for item in self.files}) != len(self.files):
            raise ValueError("A synchronization run cannot contain duplicate relative paths.")
        self._validate_outcome_counts()

    def _validate_outcome_counts(self) -> None:
        actual = {
            SyncFileOutcome.COPIED: 0,
            SyncFileOutcome.SKIPPED: 0,
            SyncFileOutcome.FAILED: 0,
            SyncFileOutcome.NOT_ATTEMPTED: 0,
            SyncFileOutcome.UNKNOWN: 0,
        }
        for item in self.files:
            if item.outcome in actual:
                actual[item.outcome] += 1

        expected = {
            SyncFileOutcome.COPIED: self.counts.copied,
            SyncFileOutcome.SKIPPED: self.counts.skipped,
            SyncFileOutcome.FAILED: self.counts.failed,
            SyncFileOutcome.NOT_ATTEMPTED: self.counts.not_attempted,
            SyncFileOutcome.UNKNOWN: self.counts.unknown,
        }
        if actual != expected:
            raise ValueError("Run counts must match the structured file outcomes.")
        if self.counts.overwritten > self.counts.copied:
            raise ValueError("Overwritten count cannot exceed copied count.")
        if self.outcome is SyncRunOutcome.IN_PROGRESS:
            if self.finished_at_utc is not None or self.duration_ms is not None:
                raise ValueError("An in-progress run cannot have finish metadata.")
            if any(item.outcome is not SyncFileOutcome.PENDING for item in self.files):
                raise ValueError("An initial run record must contain only pending files.")
        elif any(item.outcome is SyncFileOutcome.PENDING for item in self.files):
            raise ValueError("A terminal run cannot contain pending file outcomes.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "application_version": self.application_version,
            "outcome": self.outcome.value,
            "started_at_utc": self.started_at_utc,
            "finished_at_utc": self.finished_at_utc,
            "duration_ms": self.duration_ms,
            "direction": _direction_to_wire(self.direction),
            "source": self.source.to_dict(),
            "destination": self.destination.to_dict(),
            "counts": self.counts.to_dict(),
            "files": [item.to_dict() for item in self.files],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyncRunRecord":
        schema_version = int(data.get("schema_version", 0))
        if schema_version != SYNC_HISTORY_SCHEMA_VERSION:
            raise ValueError(f"Unsupported history schema version: {schema_version}")
        return cls(
            schema_version=schema_version,
            run_id=str(data["run_id"]),
            application_version=str(data["application_version"]),
            outcome=SyncRunOutcome(data["outcome"]),
            started_at_utc=str(data["started_at_utc"]),
            finished_at_utc=(str(data["finished_at_utc"]) if data.get("finished_at_utc") is not None else None),
            duration_ms=int(data["duration_ms"]) if data.get("duration_ms") is not None else None,
            direction=_direction_from_wire(str(data["direction"])),
            source=StorageEndpointSnapshot.from_dict(data["source"]),
            destination=StorageEndpointSnapshot.from_dict(data["destination"]),
            counts=SyncRunCounts.from_dict(data["counts"]),
            files=tuple(SyncFileOutcomeRecord.from_dict(item) for item in data["files"]),
        )


def utc_timestamp(value: datetime) -> str:
    """Return a stable UTC timestamp suitable for persisted history."""
    if value.tzinfo is None:
        raise ValueError("History timestamps must be timezone-aware.")
    utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _validate_utc_timestamp(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("History timestamps must use UTC.")


def _direction_to_wire(direction: SyncDirection) -> str:
    if direction is SyncDirection.LOCAL_TO_SERVER:
        return "local_to_server"
    return "server_to_local"


def _direction_from_wire(value: str) -> SyncDirection:
    directions = {
        "local_to_server": SyncDirection.LOCAL_TO_SERVER,
        "server_to_local": SyncDirection.SERVER_TO_LOCAL,
    }
    try:
        return directions[value]
    except KeyError as exc:
        raise ValueError(f"Unknown synchronization direction: {value}") from exc
