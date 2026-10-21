"""Public OAuth application identity for development and frozen builds."""
import json
import os
import re
from pathlib import Path
import sys
from uuid import UUID

ONEDRIVE_CLIENT_ID_ENV = "TRACESYNC_ONEDRIVE_CLIENT_ID"
ONEDRIVE_TENANT_ENV = "TRACESYNC_ONEDRIVE_TENANT"
GOOGLE_CLIENT_ID_ENV = "TRACESYNC_GOOGLE_CLIENT_ID"


def _value(key, environment, default=""):
    override = os.environ.get(environment, "").strip()
    if override:
        return override
    root = (Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
            if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1])
    try:
        data = json.loads((root / "provider_config.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return default
    value = data.get(key, default) if isinstance(data, dict) else default
    return value.strip() if isinstance(value, str) else default


def get_onedrive_client_id():
    return _value("onedrive_client_id", ONEDRIVE_CLIENT_ID_ENV)


def get_onedrive_tenant():
    return _value("onedrive_tenant", ONEDRIVE_TENANT_ENV, "consumers")


def get_google_client_id():
    return _value("google_drive_client_id", GOOGLE_CLIENT_ID_ENV)


def public_build_configuration(environment):
    """Emit only public identity; explicit cloud builds reject missing app IDs."""
    providers = {p.strip() for p in environment.get("TRACESYNC_BUILD_PROVIDERS", "").split(",") if p.strip()}
    if providers - {"onedrive", "google_drive"}:
        raise ValueError("Choose only implemented OneDrive or Google Drive providers for packaging.")
    result = {}
    if "google_drive" in providers:
        google_id = environment.get(GOOGLE_CLIENT_ID_ENV, "").strip()
        if not re.fullmatch(r"[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", google_id):
            raise ValueError("Set TRACESYNC_GOOGLE_CLIENT_ID to the public desktop OAuth client ID before packaging Google Drive.")
        result["google_drive_client_id"] = google_id
    if "onedrive" not in providers:
        return result
    client_id = environment.get(ONEDRIVE_CLIENT_ID_ENV, "").strip()
    try:
        if str(UUID(client_id)) != client_id.lower() or UUID(client_id).int == 0:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError("Set TRACESYNC_ONEDRIVE_CLIENT_ID to the public application UUID before packaging OneDrive.") from None
    tenant = environment.get(ONEDRIVE_TENANT_ENV, "consumers").strip()
    if tenant != "consumers":
        raise ValueError("This OneDrive build supports personal accounts (consumers) only.")
    result.update(onedrive_client_id=client_id, onedrive_tenant=tenant)
    return result
