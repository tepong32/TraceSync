from abc import ABC, abstractmethod
from enum import Enum

from models.file_record import FileRecord


class ProviderCapability(str, Enum):
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
    def scan(self) -> dict[str, FileRecord]:
        """Return the provider's files keyed by normalized relative path."""

    @abstractmethod
    def get_record(self, relative_path: str) -> FileRecord | None:
        """Return one current item, or None when it no longer exists."""

    @abstractmethod
    def destination_path(self, relative_path: str) -> str:
        """Return a safe destination identifier for a relative path."""

    @abstractmethod
    def copy_from(self, source: "StorageProvider", relative_path: str) -> None:
        """Copy one relative path from another provider into this provider."""
