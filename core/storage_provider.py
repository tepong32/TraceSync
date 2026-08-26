from abc import ABC, abstractmethod
from enum import Enum

from models.file_record import FileRecord
from models.storage_location import StorageLocation
from models.sync_history import StorageEndpointSnapshot


class ProviderCapability(str, Enum):
    """Provider declarations, not generic implementations.

    TIMESTAMPS currently feed comparison and pre-copy validation. HASHING is a
    future comparison signal. VERSION_HISTORY may later influence recovery.
    PERMISSIONS, SYMBOLIC_LINKS, and METADATA remain informational until a
    workflow explicitly consumes them.
    """

    HASHING = "hashing"
    TIMESTAMPS = "timestamps"
    VERSION_HISTORY = "version_history"
    PERMISSIONS = "permissions"
    SYMBOLIC_LINKS = "symbolic_links"
    METADATA = "metadata"


class StorageProvider(ABC):
    """Provider boundary used by scanning and synchronization services.

    Cloud and network providers can implement this interface without changing
    preview generation or job execution.
    """

    @property
    @abstractmethod
    def display_name(self) -> str:
        """A user-facing name for this storage location."""

    @property
    @abstractmethod
    def capabilities(self) -> frozenset[ProviderCapability]:
        """Features available from this provider."""

    @abstractmethod
    def describe_endpoint(self) -> StorageEndpointSnapshot:
        """Return an allowlisted, credential-free location description."""

    @abstractmethod
    def scan(self) -> dict[str, FileRecord]:
        """Return the provider's files keyed by normalized relative path."""

    @abstractmethod
    def get_record(self, relative_path: str) -> FileRecord | None:
        """Return one current item, or None when it no longer exists."""

    @abstractmethod
    def location_for(self, relative_path: str) -> StorageLocation:
        """Return this provider's native identity for one relative path."""

    def destination_path(self, relative_path: str) -> str:
        """Return legacy display text for callers that still expect a path string."""
        return self.location_for(relative_path).display_location

    @abstractmethod
    def copy_from(self, source: "StorageProvider", relative_path: str) -> None:
        """Copy one relative path from another provider into this provider."""
