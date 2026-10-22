"""Standard desktop PKCE OAuth; account-scoped Windows credentials, no Picker URL hacks."""
from dataclasses import dataclass
import hashlib
import hmac
import json
import logging
import os
from urllib.parse import parse_qs, urlsplit

from core.google_drive_provider import GOOGLE_DRIVE_SCOPE, GoogleDriveConfigurationError
from utils.provider_config import get_google_client_id


class GoogleReconnectRequired(GoogleDriveConfigurationError):
    """Saved identity cannot be renewed without explicit user interaction."""


class GoogleOAuthDiagnosticError(GoogleReconnectRequired):
    """Sanitized, stage-specific explanation for an interactive sign-in failure."""


def _with_oauth_diagnostics(flow):
    """Classify callback errors before token exchange without retaining callback data."""
    generated_state = None
    original_authorization_url = flow.authorization_url
    original_fetch_token = flow.fetch_token

    def authorization_url(**kwargs):
        nonlocal generated_state
        result = original_authorization_url(**kwargs)
        generated_state = result[1]
        return result

    def fetch_token(**kwargs):
        response = kwargs.get("authorization_response")
        try:
            query = parse_qs(urlsplit(response).query, keep_blank_values=True)
            returned_state = query.get("state", [None])[0]
            if (not isinstance(generated_state, str) or not isinstance(returned_state, str)
                    or not hmac.compare_digest(generated_state, returned_state)):
                raise GoogleOAuthDiagnosticError(
                    "Google returned an invalid sign-in response. Close the browser page and try connecting again.")

            oauth_errors = query.get("error", [])
            if oauth_errors:
                error = oauth_errors[0]
                if error == "access_denied":
                    message = "Google sign-in was canceled or permission was declined. Try again and approve read-only Drive access."
                elif error == "invalid_scope":
                    message = "Google rejected the requested Drive permission. Check the OAuth consent configuration."
                else:
                    message = "Google returned an authorization error. Check the OAuth consent configuration and try again."
                raise GoogleOAuthDiagnosticError(message)
            if not query.get("code", [None])[0]:
                raise GoogleOAuthDiagnosticError(
                    "Google returned an incomplete sign-in response. Close the browser page and try again.")
        except GoogleOAuthDiagnosticError:
            raise
        except Exception:
            raise GoogleOAuthDiagnosticError(
                "TraceSync could not validate Google's sign-in response. Try connecting again.") from None

        try:
            return original_fetch_token(**kwargs)
        except Exception:
            # Token endpoint errors may contain response bodies, client details, or codes.
            raise GoogleOAuthDiagnosticError(
                "Google sign-in reached token exchange but could not finish. Check the Desktop OAuth client and consent settings, then try again.") from None

    flow.authorization_url = authorization_url
    flow.fetch_token = fetch_token
    return flow


class GoogleTokenStore:
    """Windows Credential Manager only; never use the global keyring fallback."""
    SERVICE = "TraceSync.GoogleDrive.v2"

    def __init__(self, client_id, account_id):
        if not client_id or not account_id:
            raise GoogleDriveConfigurationError("Google application and account identity are required.")
        self.key = hashlib.sha256((client_id + "\0" + account_id).encode()).hexdigest()

    def _backend(self):
        if os.name != "nt":
            raise GoogleDriveConfigurationError("Google sign-in requires Windows protected credential storage.")
        from keyring.backends.Windows import WinVaultKeyring
        return WinVaultKeyring()

    def get(self):
        try:
            text = self._backend().get_password(self.SERVICE, self.key)
            data = json.loads(text) if text else None
            if data is not None and not isinstance(data, dict):
                raise ValueError()
            return data
        except Exception:
            raise GoogleReconnectRequired("Saved Google sign-in is unavailable. Reconnect this account.") from None

    def set(self, serialized):
        try:
            self._backend().set_password(self.SERVICE, self.key, serialized)
        except Exception:
            raise GoogleDriveConfigurationError("Windows could not protect the Google sign-in. Nothing was saved in plaintext.") from None

    def delete(self):
        try:
            backend = self._backend()
            if backend.get_password(self.SERVICE, self.key) is not None:
                backend.delete_password(self.SERVICE, self.key)
        except Exception:
            raise GoogleDriveConfigurationError("Windows could not remove this account's saved Google sign-in.") from None


@dataclass(frozen=True)
class GoogleConnection:
    account_id: str
    account_name: str
    credentials: object
    service: object


class GoogleDriveAuth:
    def __init__(self, client_id=None, store_factory=GoogleTokenStore, service_factory=None):
        self.client_id = (client_id or get_google_client_id()).strip()
        self._store_factory = store_factory
        self._service_factory = service_factory
        if not self.client_id:
            raise GoogleDriveConfigurationError("Google Drive is not configured in this build yet.")

    def _connection(self, credentials, expected_account=None):
        if self._service_factory is None:
            from googleapiclient.discovery import build
            from google_auth_httplib2 import AuthorizedHttp
            import httplib2
            # The SDK otherwise creates Http(timeout=None), leaving a worker
            # waiting indefinitely when an account or folder request stalls.
            transport = AuthorizedHttp(credentials, http=httplib2.Http(timeout=120))
            service = build("drive", "v3", http=transport, cache_discovery=False)
        else:
            service = self._service_factory(credentials)
        user = service.about().get(fields="user(permissionId,emailAddress,displayName)").execute().get("user", {})
        account_id = user.get("permissionId")
        name = user.get("emailAddress") or user.get("displayName")
        if (not isinstance(account_id, str) or not account_id.strip() or account_id != account_id.strip()
                or not isinstance(name, str) or not name.strip()):
            raise GoogleReconnectRequired("Google did not return a usable account identity.")
        if expected_account is not None and account_id != expected_account:
            raise GoogleReconnectRequired("The connected Google account does not match this Folder Pair.")
        return GoogleConnection(account_id, name.strip(), credentials, service)

    def connect(self, expected_account=None):
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
            flow = InstalledAppFlow.from_client_config({"installed": {
                "client_id": self.client_id, "client_secret": "",
                "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://127.0.0.1"]}},
                scopes=[GOOGLE_DRIVE_SCOPE], autogenerate_code_verifier=True)
            _with_oauth_diagnostics(flow)
            # The SDK's loopback handler logs request URLs at INFO, including
            # authorization codes. Suppress that logger only during this flow.
            callback_logger = logging.getLogger("google_auth_oauthlib.flow")
            quiet_callback = lambda record: False
            callback_logger.addFilter(quiet_callback)
            try:
                try:
                    credentials = flow.run_local_server(host="127.0.0.1", port=0, open_browser=True,
                        timeout_seconds=300, authorization_prompt_message="",
                        success_message="TraceSync sign-in complete. Return to the app to choose a folder.",
                        access_type="offline", prompt="consent select_account")
                except GoogleOAuthDiagnosticError:
                    raise
                except WSGITimeoutError:
                    raise GoogleOAuthDiagnosticError(
                        "No response returned to TraceSync within five minutes. Reopen the sign-in page and try again.") from None
                except Exception:
                    raise GoogleOAuthDiagnosticError(
                        "TraceSync could not start or complete its local sign-in callback. Check local security software and try again.") from None
            finally:
                callback_logger.removeFilter(quiet_callback)
            if not credentials.valid or not credentials.has_scopes([GOOGLE_DRIVE_SCOPE]):
                raise GoogleReconnectRequired("Google folder-read permission was not granted.")
            if not isinstance(credentials.refresh_token, str) or not credentials.refresh_token:
                raise GoogleReconnectRequired("Google did not provide renewable sign-in. Reconnect and approve offline access.")
            connection = self._connection(credentials, expected_account)
            self._store_factory(self.client_id, connection.account_id).set(credentials.to_json())
            return connection
        except GoogleDriveConfigurationError:
            raise
        except Exception:
            raise GoogleOAuthDiagnosticError(
                "Google sign-in could not be completed because of an unexpected local error. Try again; no sensitive details were recorded.") from None

    def acquire_for_account(self, account_id):
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            store = self._store_factory(self.client_id, account_id)
            data = store.get()
            if not data or data.get("client_id") != self.client_id:
                raise GoogleReconnectRequired("Reconnect this Folder Pair's Google account.")
            if data.get("token_uri", "https://oauth2.googleapis.com/token") != "https://oauth2.googleapis.com/token":
                raise GoogleReconnectRequired("Saved Google sign-in is invalid. Reconnect this account.")
            if GOOGLE_DRIVE_SCOPE not in data.get("scopes", []):
                raise GoogleReconnectRequired("Reconnect to grant complete folder-read access.")
            credentials = Credentials.from_authorized_user_info(data, scopes=[GOOGLE_DRIVE_SCOPE])
            if not credentials.valid:
                if not credentials.refresh_token:
                    raise GoogleReconnectRequired("Google sign-in expired. Reconnect this account.")
                # Token refresh is network I/O too; keep it bounded just like Drive API calls.
                credentials.refresh(Request(timeout=120))
            if not credentials.valid or not credentials.has_scopes([GOOGLE_DRIVE_SCOPE]):
                raise GoogleReconnectRequired("Reconnect to grant folder-read access.")
            connection = self._connection(credentials, account_id)
            store.set(credentials.to_json())
            return connection
        except GoogleDriveConfigurationError:
            raise
        except Exception:
            raise GoogleReconnectRequired("Saved Google sign-in could not be renewed. Reconnect this account.") from None

    def forget_account(self, account_id):
        # Local disconnect is account-scoped. Revoking an app grant can affect
        # other devices, so it must not be hidden inside pair deletion/disconnect.
        self._store_factory(self.client_id, account_id).delete()
