from core.scanner import scan_folder
from core.comparer import compare_folders
from models.compare_status import CompareStatus


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

    def _collect_candidates(
        self,
        results,
        allowed_statuses,
    ):
        """
        Return all ComparisonResult objects whose status is eligible
        for the requested synchronization direction.
        """

        return [
            result
            for result in results
            if result.status in allowed_statuses
        ]


    def get_local_to_server_candidates(
        self,
        results,
    ):
        return self._collect_candidates(
            results,
            {
                CompareStatus.LOCAL_NEWER,
                CompareStatus.LOCAL_ONLY,
            },
        )


    def get_server_to_local_candidates(
        self,
        results,
    ):
        return self._collect_candidates(
            results,
            {
                CompareStatus.SERVER_NEWER,
                CompareStatus.SERVER_ONLY,
            },
        )
