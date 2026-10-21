"""Resolve non-secret provider application configuration for source and builds."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


GOOGLE_CLIENT_ID_ENV = "TRACESYNC_GOOGLE_CLIENT_ID"


def get_google_client_id() -> str:
    """Read the public OAuth client ID from build data or a dev override."""
    from_environment = os.environ.get(GOOGLE_CLIENT_ID_ENV, "").strip()
    if from_environment:
        return from_environment

    if getattr(sys, "frozen", False):
        config_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        config_root = Path(__file__).resolve().parents[1]
    config_path = config_root / "provider_config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(config, dict):
        return ""
    value = config.get("google_drive_client_id", "")
    return value.strip() if isinstance(value, str) else ""
