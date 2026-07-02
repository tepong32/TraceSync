from dataclasses import dataclass
from pathlib import Path

from models.comparison_result import ComparisonResult
from models.sync_direction import SyncDirection


@dataclass
class SyncPreview:
    direction: SyncDirection
    destination: Path
    candidates: tuple[ComparisonResult, ...]

    @property
    def file_count(self) -> int:
        return len(self.candidates)