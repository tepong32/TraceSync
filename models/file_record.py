from dataclasses import dataclass


@dataclass(slots=True)
class FileRecord:
    """
    Represents a single file discovered during folder scanning.

    Attributes:
        absolute_path: Full filesystem path used for copy operations.
        relative_path: Path relative to the scanned root folder.
        modified_time: Last modified timestamp (seconds since epoch).
        size: File size in bytes.
    """

    absolute_path: str
    relative_path: str
    modified_time: float
    size: int