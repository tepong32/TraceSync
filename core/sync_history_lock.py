from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


class SyncAlreadyActiveError(RuntimeError):
    """Raised when another TraceSync process owns the synchronization lock."""


class SyncHistoryLock:
    """OS-managed exclusive lock for one active synchronization per user."""

    def __init__(self, lock_path: Path) -> None:
        self.lock_path = lock_path
        self._file: BinaryIO | None = None

    @property
    def is_acquired(self) -> bool:
        return self._file is not None

    def acquire(self) -> None:
        if self._file is not None:
            raise RuntimeError("Synchronization lock is already acquired by this instance.")
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self.lock_path.open("a+b")
        try:
            self._ensure_lock_byte(lock_file)
            _lock_file(lock_file)
        except OSError as exc:
            lock_file.close()
            raise SyncAlreadyActiveError(
                "Another TraceSync synchronization is already active."
            ) from exc
        self._file = lock_file

    def release(self) -> None:
        if self._file is None:
            return
        lock_file = self._file
        self._file = None
        try:
            _unlock_file(lock_file)
        finally:
            lock_file.close()

    @staticmethod
    def _ensure_lock_byte(lock_file: BinaryIO) -> None:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
            os.fsync(lock_file.fileno())
        lock_file.seek(0)


if os.name == "nt":
    import msvcrt

    def _lock_file(lock_file: BinaryIO) -> None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_file(lock_file: BinaryIO) -> None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_file(lock_file: BinaryIO) -> None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_file(lock_file: BinaryIO) -> None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
