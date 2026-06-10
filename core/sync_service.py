from core.scanner import scan_folder
from core.comparer import compare_folders


class SyncService:
    """
    High-level orchestration service for TraceSync.
    """

    def compare(
        self,
        local_folder: str,
        server_folder: str,
    ):
        local_files = scan_folder(local_folder)

        server_files = scan_folder(server_folder)

        return compare_folders(
            local_files,
            server_files,
        )