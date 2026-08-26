from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BackupContent:
    """Locally materialized provider content ready for durable backup storage."""

    local_path: Path
    size: int
    modified_time: float

    def __post_init__(self) -> None:
        if self.size < 0:
            raise ValueError("Backup content size cannot be negative.")
