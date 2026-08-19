import re
import sys
from pathlib import Path


UNKNOWN_VERSION = "unknown"
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def get_application_version(version_file: Path | None = None) -> str:
    """Return the packaged or source-tree VERSION without mutating it."""
    candidates = [version_file] if version_file is not None else _version_candidates()

    for candidate in candidates:
        if candidate is None:
            continue
        try:
            version = candidate.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if _VERSION_PATTERN.fullmatch(version):
            return version

    return UNKNOWN_VERSION


def _version_candidates() -> list[Path]:
    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "VERSION")
    candidates.append(Path(__file__).resolve().parents[1] / "VERSION")
    return candidates
