from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from enum import Enum

from models.file_record import FileRecord
from models.backup_content import BackupContent
from models.storage_location import StorageLocation
from models.sync_history import StorageEndpointSnapshot
from models.transfer_precondition import TransferPrecondition


class TransferPreconditionTarget(str, Enum):
    SOURCE = "source"
    DESTINATION = "destination"


class TransferError(RuntimeError):
    """Base class for provider-neutral transfer failures."""


class TransferFailed(TransferError):
    """The provider could not complete a transfer for an operational reason."""


class TransferOutcomeUnknown(TransferError):
    """The provider cannot determine whether the transfer committed."""


class TransferPreconditionFailed(TransferError):
    """The reviewed source or destination state no longer matches."""

    def __init__(
        self,
        target: TransferPreconditionTarget,
        message: str = "The item changed after it was reviewed.",
    ) -> None:
        super().__init__(message)
        self.target = target


class ConditionalTransferUnsupported(TransferError):
    """The provider cannot guarantee transfer preconditions."""


class ProviderCapability(str, Enum):
    """Provider declarations, not generic implementations.

    TIMESTAMPS declares timestamps reliable enough for ordering and validation.
    HASHING enables content-hash equality and change checks. VERSION_HISTORY
    enables provider version IDs for same-item validation and may later support recovery.
    CONDITIONAL_CREATE declares that create operations enforce reviewed absence.
    CONDITIONAL_TRANSFER declares that both create and replacement operations
    enforce reviewed source and destination preconditions as part of the transfer.
    PERMISSIONS, SYMBOLIC_LINKS, and METADATA remain informational until a
    workflow explicitly consumes them.
    """

    HASHING = "hashing"
    TIMESTAMPS = "timestamps"
    VERSION_HISTORY = "version_history"
    CONDITIONAL_CREATE = "conditional_create"
    CONDITIONAL_TRANSFER = "conditional_transfer"
    PERMISSIONS = "permissions"
    SYMBOLIC_LINKS = "symbolic_links"
    METADATA = "metadata"


class StorageProvider(ABC):
    """Provider boundary used by scanning and synchronization services.

    Cloud and network providers can implement this interface without changing
    preview generation or job execution.
    """

    # Workflow restriction in either direction, independent of transfer capabilities.
    create_only = False

    def begin_transfer_run(self):
        """Reset run-owned transient state without remote mutations."""

    def folder_plan(self, relative_path):
        """Immutable (relative path, existing native ID or expected absence) evidence."""
        return ()

    def transfer_notes(self, relative_path):
        """Credential-free partial side effects for per-file history."""
        return ""

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

    def open_backup_content(
        self,
        relative_path: str,
    ) -> AbstractContextManager[BackupContent]:
        """Materialize and verify existing content for durable local backup.

        Providers that cannot safely supply the current content must leave this
        unsupported so overwrite protection fails closed.
        """
        raise NotImplementedError(
            "This provider cannot safely supply existing content for backup."
        )

    def open_transfer_content(
        self,
        relative_path: str,
        precondition: TransferPrecondition,
    ) -> AbstractContextManager[BackupContent]:
        """Materialize source content that satisfies the reviewed precondition.

        The context may expose a direct local path or a verified temporary file.
        Providers that cannot supply reviewed content must fail closed.
        """
        raise ConditionalTransferUnsupported(
            "This provider cannot supply reviewed content for transfer."
        )

    def transfer_from(
        self,
        source: "StorageProvider",
        relative_path: str,
        precondition: TransferPrecondition,
    ) -> None:
        """Transfer only when the reviewed source and destination state still holds.

        Returning successfully guarantees that the provider enforced the supplied
        precondition during its create or replacement operation.
        """
        raise ConditionalTransferUnsupported(
            "This provider cannot guarantee a conditional transfer."
        )
