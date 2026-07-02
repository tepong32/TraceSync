from pathlib import Path

from core.comparer import compare_folders
from core.scanner import scan_folder
from models.compare_status import CompareStatus
from models.comparison_result import ComparisonResult
from models.sync_direction import SyncDirection
from models.sync_preview import SyncPreview


class SyncService:
    """
    High-level orchestration service for TraceSync.
    """

    def compare(
        self,
        local_folder: str,
        server_folder: str,
    ) -> list[ComparisonResult]:
        local_files = scan_folder(local_folder)
        server_files = scan_folder(server_folder)

        return compare_folders(
            local_files,
            server_files,
        )

    def get_sync_preview(
        self,
        results: list[ComparisonResult],
        direction: SyncDirection,
        local_folder: Path,
        server_folder: Path,
    ) -> SyncPreview:
        """
        Build a synchronization preview for the requested direction.

        This method centralizes all synchronization eligibility rules
        and returns a read-only snapshot for the UI.
        """

        candidates = tuple(
            self._collect_candidates(results, direction)
        )

        destination = (
            server_folder
            if direction is SyncDirection.LOCAL_TO_SERVER
            else local_folder
        )

        return SyncPreview(
            direction=direction,
            destination=destination,
            candidates=candidates,
        )

    def _collect_candidates(
        self,
        results: list[ComparisonResult],
        direction: SyncDirection,
    ) -> list[ComparisonResult]:
        """
        Return all ComparisonResult objects eligible for the requested
        synchronization direction.
        """

        if direction is SyncDirection.LOCAL_TO_SERVER:
            allowed_statuses = {
                CompareStatus.LOCAL_NEWER,
                CompareStatus.LOCAL_ONLY,
            }
        else:
            allowed_statuses = {
                CompareStatus.SERVER_NEWER,
                CompareStatus.SERVER_ONLY,
            }

        return [
            result
            for result in results
            if result.status in allowed_statuses
        ]

    def get_local_to_server_candidates(
        self,
        results: list[ComparisonResult],
    ) -> list[ComparisonResult]:
        """
        Backwards-compatible wrapper.
        """

        return self._collect_candidates(
            results,
            SyncDirection.LOCAL_TO_SERVER,
        )

    def get_server_to_local_candidates(
        self,
        results: list[ComparisonResult],
    ) -> list[ComparisonResult]:
        """
        Backwards-compatible wrapper.
        """

        return self._collect_candidates(
            results,
            SyncDirection.SERVER_TO_LOCAL,
        )