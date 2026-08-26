from dataclasses import dataclass

from models.comparison_metadata import ComparisonMetadata
from models.storage_location import StorageLocation


@dataclass(slots=True)
class FileRecord:
    """
    Represents a single file discovered during folder scanning.

    Attributes:
        absolute_path: Compatibility display value for existing local callers.
        relative_path: Path relative to the scanned root folder.
        modified_time: Compatibility timestamp value when provided.
        size: Compatibility size value when provided.
        location: Provider-neutral item identity and display location.
        comparison_metadata: Provider-reported comparison evidence.
    """

    absolute_path: str
    relative_path: str
    modified_time: float | None
    size: int | None
    location: StorageLocation | None = None
    comparison_metadata: ComparisonMetadata | None = None

    def __post_init__(self) -> None:
        if self.location is None:
            # Existing FileRecord constructors represented local filesystem paths.
            self.location = StorageLocation.local(self.absolute_path, resolve=False)
        if self.comparison_metadata is None:
            self.comparison_metadata = ComparisonMetadata(
                size=self.size,
                modified_time=self.modified_time,
                timestamp_reliable=self.modified_time is not None,
            )
        else:
            if self.size is None:
                self.size = self.comparison_metadata.size
            elif (
                self.comparison_metadata.size is not None
                and self.size != self.comparison_metadata.size
            ):
                raise ValueError("File size must match its comparison metadata.")
            if self.modified_time is None:
                self.modified_time = self.comparison_metadata.modified_time
            elif (
                self.comparison_metadata.modified_time is not None
                and self.modified_time != self.comparison_metadata.modified_time
            ):
                raise ValueError("File timestamp must match its comparison metadata.")

    @property
    def storage_location(self) -> StorageLocation:
        location = self.location
        if location is None:
            raise RuntimeError("File record has no storage location.")
        return location

    @property
    def display_location(self) -> str:
        return self.storage_location.display_location

    @property
    def metadata(self) -> ComparisonMetadata:
        metadata = self.comparison_metadata
        if metadata is None:
            raise RuntimeError("File record has no comparison metadata.")
        return metadata

    @classmethod
    def from_location(
        cls,
        location: StorageLocation,
        relative_path: str,
        modified_time: float | None,
        size: int | None,
        comparison_metadata: ComparisonMetadata | None = None,
    ) -> "FileRecord":
        return cls(
            absolute_path=location.display_location,
            relative_path=relative_path,
            modified_time=modified_time,
            size=size,
            location=location,
            comparison_metadata=comparison_metadata,
        )
