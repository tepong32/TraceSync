from core.local_storage_provider import LocalStorageProvider
from models.file_record import FileRecord


def scan_folder(folder_path: str) -> dict[str, FileRecord]:
    """
    Recursively scans a folder and returns a dictionary of FileRecords.

    Dictionary keys are relative paths, which serve as the unique identity
    of each file within TraceSync.

    Example:
        {
            "Reports/June/report.xlsx": FileRecord(...),
            "HR/employees.xlsx": FileRecord(...)
        }
    """

    return LocalStorageProvider(folder_path, "Folder").scan()
