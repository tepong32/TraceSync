from pathlib import Path

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

    root = Path(folder_path)

    if not root.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder_path}")

    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    records: dict[str, FileRecord] = {}

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue

        try:
            stat = file_path.stat()

            relative_path = file_path.relative_to(root).as_posix()

            records[relative_path] = FileRecord(
                absolute_path=str(file_path.resolve()),
                relative_path=relative_path,
                modified_time=stat.st_mtime,
                size=stat.st_size,
            )

        except (PermissionError, OSError):
            # Skip files that cannot be read.
            continue

    return records