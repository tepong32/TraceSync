"""Credential storage adapters; credentials never belong in settings/history."""

from __future__ import annotations

import json


class GoogleTokenStore:
    """Store Google OAuth refresh credentials in the OS credential manager."""

    SERVICE_NAME = "TraceSync.GoogleDrive"
    USER_NAME = "oauth-credentials"

    def get(self) -> dict | None:
        import keyring

        value = keyring.get_password(self.SERVICE_NAME, self.USER_NAME)
        if not value:
            return None
        try:
            data = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            self.delete()
            return None
        return data if isinstance(data, dict) else None

    def set(self, serialized_credentials: str) -> None:
        import keyring

        keyring.set_password(self.SERVICE_NAME, self.USER_NAME, serialized_credentials)

    def delete(self) -> None:
        import keyring

        try:
            keyring.delete_password(self.SERVICE_NAME, self.USER_NAME)
        except keyring.errors.PasswordDeleteError:
            pass
