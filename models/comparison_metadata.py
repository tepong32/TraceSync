from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComparisonMetadata:
    """Provider-reported evidence for comparison and change detection."""

    size: int | None = None
    modified_time: float | None = None
    content_hash: str | None = None
    hash_algorithm: str | None = None
    version_id: str | None = None
    timestamp_reliable: bool = False

    def __post_init__(self) -> None:
        if self.size is not None and self.size < 0:
            raise ValueError("Comparison size cannot be negative.")
        for value, label in (
            (self.content_hash, "Content hash"),
            (self.hash_algorithm, "Hash algorithm"),
            (self.version_id, "Provider version ID"),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"{label} cannot be empty.")
        if (self.content_hash is None) != (self.hash_algorithm is None):
            raise ValueError("Content hash and hash algorithm must be provided together.")
        if self.timestamp_reliable and self.modified_time is None:
            raise ValueError("A reliable timestamp requires a modified time.")
