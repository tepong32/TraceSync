from enum import Enum


class SyncDirection(str, Enum):
    """The one-way direction for a synchronization run."""

    LOCAL_TO_SERVER = "Local to Server"
    SERVER_TO_LOCAL = "Server to Local"

    @property
    def display_name(self) -> str:
        if self is SyncDirection.LOCAL_TO_SERVER:
            return "Local → Server"
        return "Server → Local"
