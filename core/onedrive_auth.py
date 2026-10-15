"""Microsoft public-client authentication backed by the OS credential store."""

from __future__ import annotations

import os
from pathlib import Path


CLIENT_ID_ENV = "TRACESYNC_ONEDRIVE_CLIENT_ID"
TENANT_ENV = "TRACESYNC_ONEDRIVE_TENANT"
GRAPH_SCOPES = ["User.Read", "Files.ReadWrite"]


class OneDriveConfigurationError(RuntimeError):
    """OneDrive app registration or delegated account setup is missing."""


class OneDriveAuth:
    """Acquire and cache delegated Graph tokens for a desktop public client."""

    def __init__(self, token_store, client_id: str | None = None, tenant: str | None = None):
        self.client_id = (client_id or os.environ.get(CLIENT_ID_ENV, "")).strip()
        self.tenant = (tenant or os.environ.get(TENANT_ENV, "common")).strip()
        self.token_store = token_store
        self._app = None
        if not self.client_id:
            raise OneDriveConfigurationError(
                f"Set {CLIENT_ID_ENV} to your Microsoft desktop app client ID."
            )
        if not self.tenant:
            raise OneDriveConfigurationError(f"Set {TENANT_ENV} or use 'common'.")

    def connect(self) -> tuple[str, dict]:
        import msal

        cache = self.token_store.create_cache()
        app = msal.PublicClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant}",
            token_cache=cache,
        )
        accounts = app.get_accounts()
        result = app.acquire_token_silent(GRAPH_SCOPES, account=accounts[0]) if accounts else None
        if not result or "access_token" not in result:
            result = app.acquire_token_interactive(scopes=GRAPH_SCOPES, prompt="select_account")
        if "access_token" not in result:
            # Keep provider details and tokens out of dialogs, logs, and history.
            error = result.get("error", "sign_in_failed")
            code = result.get("error_codes", [])
            suffix = f" ({code[0]})" if code else ""
            raise OneDriveConfigurationError(
                f"Microsoft sign-in did not complete: {error}{suffix}. Check the app registration and try again."
            )
        self._app = app
        return result["access_token"], result

    def disconnect(self) -> None:
        if self._app is not None:
            for account in self._app.get_accounts():
                self._app.remove_account(account)
            self._app = None
        self.token_store.delete()


class OneDriveTokenStore:
    """Persist the MSAL cache encrypted with Windows DPAPI and file locking."""

    def __init__(self, cache_path: Path | None = None) -> None:
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        self.cache_path = cache_path or local_app_data / "TraceSync" / "onedrive-token-cache.bin"

    def create_cache(self):
        from msal_extensions import PersistedTokenCache, build_encrypted_persistence

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        persistence = build_encrypted_persistence(str(self.cache_path))
        if not persistence.is_encrypted:
            raise OneDriveConfigurationError(
                "Windows could not protect the Microsoft sign-in cache. OneDrive sign-in was stopped."
            )
        return PersistedTokenCache(persistence)

    def delete(self) -> None:
        self.cache_path.unlink(missing_ok=True)
