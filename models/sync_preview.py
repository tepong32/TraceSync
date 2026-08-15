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
    decision_recommendation: str | None = None
    decision_confidence: str | None = None
    decision_reason: str | None = None
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

    @property
    def low_confidence_count(self) -> int:
        return sum(item.decision_confidence == "Low" for item in self.items)

    def with_selected_items(self, selected_relative_paths: set[str]) -> "SyncPreview":
        selected_items = tuple(
            item
            for item in self.items
            if item.relative_path in selected_relative_paths
        )
        return SyncPreview(
            direction=self.direction,
            items=selected_items,
            warnings=tuple(self._build_warnings(selected_items)),
        )

    @staticmethod
    def _build_warnings(items: tuple[SyncPreviewItem, ...]) -> list[str]:
        warnings: list[str] = []
        overwrites = sum(item.overwrite for item in items)
        if overwrites:
            warnings.append(f"{overwrites} existing file(s) will be replaced.")
        if not items:
            warnings.append("No files were selected for synchronization.")
        return warnings
