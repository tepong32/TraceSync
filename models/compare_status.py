from enum import Enum


class CompareStatus(str, Enum):
    """
    Standard comparison result statuses used throughout TraceSync.

    Inheriting from str allows direct use in Treeviews, JSON exports,
    logging, filtering, and display labels without extra conversion.
    """

    SAME = "Same"
    LOCAL_NEWER = "Local Newer"
    SERVER_NEWER = "Server Newer"
    LOCAL_ONLY = "Local Only"
    SERVER_ONLY = "Server Only"

    @classmethod
    def all(cls):
        return list(cls)