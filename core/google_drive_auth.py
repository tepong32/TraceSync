"""Google desktop OAuth and Picker flow for selecting an accessible Drive folder."""

from __future__ import annotations

from http import HTTPStatus
from urllib.parse import parse_qs
from time import monotonic
import webbrowser
from wsgiref.simple_server import WSGIRequestHandler, make_server

from core.google_drive_provider import (
    GOOGLE_DRIVE_SCOPE,
    GoogleDriveConfigurationError,
)
from utils.provider_config import GOOGLE_CLIENT_ID_ENV, get_google_client_id


class GoogleDrivePickerCancelled(RuntimeError):
    """The user closed or cancelled the Google sign-in/Picker flow."""


class _QuietRequestHandler(WSGIRequestHandler):
    def log_message(self, _format, *args):
        # Avoid writing OAuth callback parameters, including the one-time code,
        # to the application's console/log stream.
        return


def authenticate_and_pick_folder(token_store, client_id: str | None = None):
    """Authenticate with PKCE and return credentials plus one picked folder.

    Google desktop Picker returns a selected folder ID through the loopback
    redirect. The ID is resolved through Drive API before this function returns
    so a file selection cannot accidentally be used as a folder endpoint.
    """
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_id = (client_id or get_google_client_id()).strip()
    if not client_id:
        raise GoogleDriveConfigurationError(
            f"Set {GOOGLE_CLIENT_ID_ENV} to your Google desktop OAuth client ID."
        )

    # A saved token cannot grant access to a newly selected folder. Force
    # Picker consent on each explicit folder-selection action.
    credentials, picked_ids = _run_picker_flow(InstalledAppFlow, client_id)

    if len(picked_ids) != 1:
        raise GoogleDrivePickerCancelled("Choose exactly one Google Drive folder to continue.")

    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    folder = drive.files().get(
        fileId=picked_ids[0],
        fields="id,name,mimeType,trashed,capabilities(canListChildren)",
        supportsAllDrives=True,
    ).execute()
    if folder.get("trashed") or folder.get("mimeType") != "application/vnd.google-apps.folder":
        raise GoogleDriveConfigurationError("Select a Google Drive folder, not an individual file.")
    if folder.get("capabilities", {}).get("canListChildren") is not True:
        raise GoogleDriveConfigurationError(
            "Google Drive did not grant TraceSync access to list this folder's contents. Choose another folder."
        )
    account = drive.about().get(fields="user(emailAddress)").execute()
    account_email = account.get("user", {}).get("emailAddress", "Google account")
    token_store.set(credentials.to_json())
    return credentials, {
        "folder_id": folder["id"],
        "folder_name": folder.get("name", "Google Drive folder"),
        "account_email": account_email,
    }


def revoke_google_sign_in(token_store) -> bool:
    """Revoke the stored Google credential when possible, then clear local storage."""
    import requests

    credential_data = token_store.get() or {}
    token = credential_data.get("refresh_token") or credential_data.get("token")
    revoked = not token
    try:
        if token:
            response = requests.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": token},
                timeout=10,
            )
            revoked = response.status_code == HTTPStatus.OK
    except requests.RequestException:
        revoked = False
    finally:
        token_store.delete()
    return revoked


def _run_picker_flow(flow_type, client_id: str):
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = flow_type.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                # Desktop clients are public clients. A secret is not required
                # and must not be treated as confidential in a desktop app.
                "client_secret": "",
                "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://127.0.0.1"],
            }
        },
        scopes=[GOOGLE_DRIVE_SCOPE],
    )
    callback: dict[str, list[str]] = {}

    def application(environ, start_response):
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        if "code" in query or "error" in query:
            callback.update(query)
        body = (
            b"Google Drive folder selection complete. You can close this browser tab."
            if callback.get("code")
            else b"Google Drive authorization was cancelled. You can close this browser tab."
        )
        start_response(
            f"{HTTPStatus.OK.value} {HTTPStatus.OK.phrase}",
            [("Content-Type", "text/plain; charset=utf-8"), ("Content-Length", str(len(body)))],
        )
        return [body]

    server = make_server("127.0.0.1", 0, application, handler_class=_QuietRequestHandler)
    flow.redirect_uri = f"http://127.0.0.1:{server.server_port}/"
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent select_account",
        include_granted_scopes="false",
        trigger_onepick="true",
        allow_folder_selection="true",
    )
    try:
        if not webbrowser.open(authorization_url, new=1, autoraise=True):
            raise GoogleDriveConfigurationError(
                "TraceSync could not open the system browser for Google sign-in."
            )
        deadline = monotonic() + 300
        server.timeout = 1
        while not ("code" in callback or "error" in callback) and monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()

    if callback.get("error"):
        raise GoogleDrivePickerCancelled("Google Drive sign-in or folder selection was cancelled.")
    code = callback.get("code", [""])[0]
    returned_state = callback.get("state", [""])[0]
    picked = callback.get("picked_file_ids", [""])[0]
    picked_ids = [item.strip() for item in picked.split(",") if item.strip()]
    if not code or returned_state != state:
        raise GoogleDriveConfigurationError(
            "Google sign-in did not return a valid authorization response. Try connecting again."
        )
    flow.fetch_token(code=code)
    return flow.credentials, picked_ids
