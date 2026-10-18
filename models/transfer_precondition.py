from dataclasses import dataclass

from models.comparison_metadata import ComparisonMetadata
from models.storage_location import StorageLocation


@dataclass(frozen=True, slots=True)
class TransferPrecondition:
    """Reviewed identities and state that must still hold for one transfer."""

    source_location: StorageLocation
    source_metadata: ComparisonMetadata
    destination_location: StorageLocation
    destination_metadata: ComparisonMetadata | None
    destination_folders: tuple[tuple[str, str | None], ...] = ()

    @property
    def expects_destination_absent(self) -> bool:
        return self.destination_metadata is None
