from dataclasses import dataclass

from models.storage_location import StorageLocation


@dataclass(slots=True)
class FileRecord:
    """
    Represents a single file discovered during folder scanning.

    Attributes:
        absolute_path: Compatibility display value for existing local callers.
        relative_path: Path relative to the scanned root folder.
        modified_time: Last modified timestamp (seconds since epoch).
        size: File size in bytes.
        location: Provider-neutral item identity and display location.
    """

    absolute_path: str
    relative_path: str
    modified_time: float
    size: int
    location: StorageLocation | None = None

    def __post_init__(self) -> None:
        if self.location is None:
            # Existing FileRecord constructors represented local filesystem paths.
            self.location = StorageLocation.local(self.absolute_path, resolve=False)

    @property
    def storage_location(self) -> StorageLocation:
        location = self.location
        if location is None:
            raise RuntimeError("File record has no storage location.")
        return location

    @property
    def display_location(self) -> str:
        return self.storage_location.display_location

    @classmethod
    def from_location(
        cls,
        location: StorageLocation,
        relative_path: str,
        modified_time: float,
        size: int,
    ) -> "FileRecord":
        return cls(
            absolute_path=location.display_location,
            relative_path=relative_path,
            modified_time=modified_time,
            size=size,
            location=location,
        )
