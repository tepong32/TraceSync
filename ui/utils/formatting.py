from __future__ import annotations

import mimetypes
from datetime import datetime

from models.comparison_decision import ConfidenceLevel


def format_timestamp(timestamp: float | int | None) -> str:
    """Return a readable local timestamp string."""
    if timestamp is None:
        return "Not Available"
    try:
        return datetime.fromtimestamp(float(timestamp)).strftime("%b %d, %Y %I:%M:%S %p")
    except (OSError, TypeError, ValueError):
        return "Invalid timestamp"


def format_bytes(size: int | float | None) -> str:
    """Return file size in human-readable units."""
    if size is None:
        return "—"
    try:
        value = float(size)
    except (TypeError, ValueError):
        return "—"
    if value < 0:
        return "—"

    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while value >= 1024 and index < len(units) - 1:
        value /= 1024
        index += 1

    if units[index] == "B":
        return f"{int(value)} {units[index]}"
    return f"{value:.2f} {units[index]}"


def format_file_type(path: str | None) -> str:
    """Return a lightweight file-type label from a path."""
    if not path or path == "Not Available" or path == "—":
        return "Unknown"

    mime_type, _ = mimetypes.guess_type(path)
    if mime_type:
        major_minor = mime_type.split("/")
        return major_minor[-1].replace("-", " ").upper()

    return "Unknown"


def format_decision_recommendation(recommendation: str | None) -> str:
    if not recommendation:
        return "Review before synchronizing."
    return recommendation


def format_decision_confidence(confidence: str | ConfidenceLevel | None) -> str:
    if not confidence:
        return "Review needed"

    if isinstance(confidence, ConfidenceLevel):
        confidence = confidence.value

    return {
        "High": "Likely safe",
        "Medium": "Needs review",
        "Low": "Needs attention",
    }.get(str(confidence), str(confidence))


def format_decision_reason(reason: str | None) -> str:
    if not reason:
        return "Review before synchronizing because details are not yet available."

    normalized = str(reason).strip()
    if "available metadata" in normalized:
        return "TraceSync could not determine the safest direction with the available information. Please review this file."

    if "could not confidently classify" in normalized:
        return "TraceSync could not determine the safest direction with confidence. Please review this file."

    return normalized
