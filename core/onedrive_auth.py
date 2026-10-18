"""Microsoft public-client authentication backed by the OS credential store."""

from __future__ import annotations

import os
from pathlib import Path


CLIENT_ID_ENV = "TRACESYNC_ONEDRIVE_CLIENT_ID"
TENANT_ENV = "TRACESYNC_ONEDRIVE_TENANT"
GRAPH_SCOPES = ["User.Read", "Files.ReadWrite"]


class OneDriveConfigurationError(RuntimeError):
    """OneDrive app registration or delegated account setup is missing."""


class OneDriveReconnectRequired(OneDriveConfigurationError):
    """The saved account needs explicit sign-in; never choose another account."""


class OneDriveAuth:
    """Acquire and cache delegated Graph tokens for a desktop public client."""

    def __init__(self, token_store, client_id: str | None = None, tenant: str | None = None):
        self.client_id = (client_id or os.environ.get(CLIENT_ID_ENV, "")).strip()
        self.tenant = (tenant or os.environ.get(TENANT_ENV, "consumers")).strip()
        self.token_store = token_store
        self._app = None
        self.account_reference = ""
        if not self.client_id:
            raise OneDriveConfigurationError(
                "OneDrive connection is not configured in this build yet."
            )
        if not self.tenant:
            raise OneDriveConfigurationError(f"Set {TENANT_ENV} or use 'consumers'.")

    def _application(self):
        import msal
        if self._app is None:
            self._app = msal.PublicClientApplication(
                self.client_id,
                authority=f"https://login.microsoftonline.com/{self.tenant}",
                token_cache=self.token_store.create_cache(),
            )
        return self._app

    def connect(self) -> tuple[str, dict]:
        self.account_reference = ""
        app = self._application()
        result = app.acquire_token_interactive(scopes=GRAPH_SCOPES, prompt="select_account")
        if not result or "access_token" not in result:
            raise OneDriveConfigurationError(
                "Microsoft sign-in did not complete. Please try connecting again."
            )
        # Bind the interactive result to one cache entry. Display names/emails
        # alone are not an account identity. Missing claims disable silent reuse.
        claims = result.get("id_token_claims", {})
        local_id = claims.get("oid") or claims.get("sub")
        tenant_id = claims.get("tid")
        accounts = app.get_accounts() if local_id and tenant_id else []
        matches = [account for account in accounts
                   if account.get("local_account_id") == local_id
                   and account.get("realm") == tenant_id]
        if len(matches) == 1:
            self.account_reference = matches[0].get("home_account_id", "")
        return result["access_token"], result

    def acquire_for_account(self, account_reference: str, *, interactive=False):
        """Refresh only an exact cache account; browser fallback is opt-in."""
        self.account_reference = ""
        if not account_reference:
            raise OneDriveReconnectRequired("Reconnect the saved Microsoft account.")
        app = self._application()
        if interactive:
            token, result = self.connect()
            if self.account_reference != account_reference:
                self.account_reference = ""
                raise OneDriveReconnectRequired("The selected Microsoft account does not match this Folder Pair.")
            return token, result
        matches = [account for account in app.get_accounts()
                   if account.get("home_account_id") == account_reference]
        if len(matches) != 1:
            raise OneDriveReconnectRequired("Reconnect the Microsoft account saved with this Folder Pair.")
        try:
            result = app.acquire_token_silent(GRAPH_SCOPES, account=matches[0])
        except Exception:
            raise OneDriveReconnectRequired("The saved account could not be renewed. Reconnect to continue.") from None
        if not result or not result.get("access_token"):
            raise OneDriveReconnectRequired("The saved account needs permission again. Reconnect to continue.")
        self.account_reference = account_reference
        return result["access_token"], result

    def forget_account(self, account_reference: str):
        """Remove this account's cache entries, retaining other signed-in accounts."""
        if not account_reference:
            raise OneDriveReconnectRequired("Reconnect this account before disconnecting its saved sign-in.")
        app = self._application()
        for account in app.get_accounts():
            if account.get("home_account_id") == account_reference:
                app.remove_account(account)
        if self.account_reference == account_reference:
            self.account_reference = ""

    def disconnect(self) -> None:
        if self._app is not None:
            for account in self._app.get_accounts():
                self._app.remove_account(account)
            self._app = None
        self.token_store.delete()
        self.account_reference = ""


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
