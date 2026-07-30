from dataclasses import dataclass
from enum import Enum

from models.compare_status import CompareStatus
from models.sync_direction import SyncDirection


class SyncOperation(str, Enum):
    COPY = "Copy"


@dataclass(frozen=True, slots=True)
class SyncPreviewItem:
    """One file operation approved for a synchronization job."""

    relative_path: str
    source: str
    destination: str
    direction: SyncDirection
    comparison_status: CompareStatus
    operation: SyncOperation
    overwrite: bool
    reason: str
    source_modified_time: float | None = None
    source_size: int | None = None
    destination_modified_time: float | None = None
    destination_size: int | None = None


@dataclass(frozen=True, slots=True)
class SyncPreview:
    """An immutable, reusable plan generated before any file is copied."""

    direction: SyncDirection
    items: tuple[SyncPreviewItem, ...]
    warnings: tuple[str, ...] = ()

    @property
    def create_count(self) -> int:
        return sum(not item.overwrite for item in self.items)

    @property
    def overwrite_count(self) -> int:
        return sum(item.overwrite for item in self.items)

    @property
    def total_files(self) -> int:
        return len(self.items)
