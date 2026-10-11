"""Publish a fully staged file without replacing an occupied destination."""

import os
from os import name as OS_NAME
from pathlib import Path


def publish_new_file(staged_path: Path, destination_path: Path) -> None:
    """Atomically require absence; never fall back to an overwriting operation.

    Both paths must be on the same filesystem. Windows rename refuses an
    existing destination. POSIX rename does not, so use exclusive hard-link
    creation there and leave staging-name cleanup to the caller. Unsupported
    filesystems fail safely instead of exposing a partial destination.
    """
    if OS_NAME == "nt":
        os.rename(staged_path, destination_path)
    else:
        os.link(staged_path, destination_path)
