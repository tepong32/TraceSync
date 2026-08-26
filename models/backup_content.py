from dataclasses import dataclass
from pathlib import Path

from models.comparison_metadata import ComparisonMetadata


@dataclass(frozen=True, slots=True)
class BackupContent:
    """Provider content plus the local materialization used for safe copying.

    Size and modified_time describe the local materialized file. Provider-reported
    comparison evidence remains separate in comparison_metadata.
    """

    local_path: Path
    size: int
    modified_time: float
    comparison_metadata: ComparisonMetadata

    def __post_init__(self) -> None:
        if self.size < 0:
            raise ValueError("Backup content size cannot be negative.")
        if (
            self.comparison_metadata.size is not None
            and self.comparison_metadata.size != self.size
        ):
            raise ValueError(
                "Materialized content size must match provider comparison metadata."
            )

    @property
    def materialized_size(self) -> int:
        return self.size

    @property
    def materialized_modified_time(self) -> float:
        return self.modified_time
