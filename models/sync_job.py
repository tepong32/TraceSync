from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from time import monotonic


class SyncJobStatus(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    COMPLETED_WITH_ERRORS = "Completed with errors"


@dataclass(frozen=True, slots=True)
class SyncError:
    relative_path: str
    message: str


@dataclass(frozen=True, slots=True)
class SyncSummary:
    copied_files: int
    overwritten_files: int
    skipped_files: int
    errors: tuple[SyncError, ...]
    elapsed_seconds: float
    cancelled: bool


@dataclass(frozen=True, slots=True)
class SyncJobSnapshot:
    status: SyncJobStatus
    current_file: str
    completed_files: int
    total_files: int
    elapsed_seconds: float
    percentage: float
    is_finished: bool


@dataclass(slots=True)
class SyncJob:
    """Mutable state for a synchronization run, observed by the UI."""

    total_files: int
    status: SyncJobStatus = SyncJobStatus.PENDING
    current_file: str = ""
    completed_files: int = 0
    copied_files: int = 0
    overwritten_files: int = 0
    skipped_files: int = 0
    errors: list[SyncError] = field(default_factory=list)
    cancellation_requested: bool = False
    started_at: float | None = None
    finished_at: float | None = None
    lock: RLock = field(default_factory=RLock, init=False, repr=False, compare=False)

    def request_cancel(self) -> None:
        with self.lock:
            self.cancellation_requested = True

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        return (self.finished_at or monotonic()) - self.started_at

    @property
    def percentage(self) -> float:
        if not self.total_files:
            return 100.0
        return self.completed_files / self.total_files * 100

    @property
    def is_finished(self) -> bool:
        return self.status in {
            SyncJobStatus.COMPLETED,
            SyncJobStatus.CANCELLED,
            SyncJobStatus.COMPLETED_WITH_ERRORS,
        }

    def summary(self) -> SyncSummary:
        with self.lock:
            return SyncSummary(
                copied_files=self.copied_files,
                overwritten_files=self.overwritten_files,
                skipped_files=self.skipped_files,
                errors=tuple(self.errors),
                elapsed_seconds=self.elapsed_seconds,
                cancelled=self.status is SyncJobStatus.CANCELLED,
            )

    def snapshot(self) -> SyncJobSnapshot:
        """Return a consistent worker-state snapshot for the Tkinter thread."""
        with self.lock:
            elapsed_seconds = self.elapsed_seconds
            percentage = self.percentage
            is_finished = self.is_finished
            return SyncJobSnapshot(
                status=self.status,
                current_file=self.current_file,
                completed_files=self.completed_files,
                total_files=self.total_files,
                elapsed_seconds=elapsed_seconds,
                percentage=percentage,
                is_finished=is_finished,
            )
