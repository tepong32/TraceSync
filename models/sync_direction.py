from enum import Enum


class SyncDirection(Enum):
    """Represents the direction of a synchronization operation."""

    LOCAL_TO_SERVER = "local_to_server"
    SERVER_TO_LOCAL = "server_to_local"

    @property
    def label(self) -> str:
        """Returns a human-readable label for the synchronization direction."""
        return (
            "Local → Server"
            if self is SyncDirection.LOCAL_TO_SERVER
            else "Server → Local"
        )