import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.onedrive_auth import OneDriveAuth, OneDriveConfigurationError, OneDriveTokenStore


class OneDriveAuthTests(unittest.TestCase):
    def test_connect_uses_personal_public_client_and_explicit_account_choice(self):
        msal = Mock()
        app = msal.PublicClientApplication.return_value
        app.acquire_token_interactive.return_value = {"access_token": "test-only"}
        store = Mock()
        with patch.dict(sys.modules, {"msal": msal}), patch.dict("os.environ", {}, clear=True):
            auth = OneDriveAuth(store, client_id="application-id")
            self.assertEqual(auth.connect()[0], "test-only")
        self.assertEqual(msal.PublicClientApplication.call_args.kwargs["authority"],
                         "https://login.microsoftonline.com/consumers")
        self.assertNotIn("client_credential", msal.PublicClientApplication.call_args.kwargs)
        self.assertEqual(app.acquire_token_interactive.call_args.kwargs["prompt"], "select_account")
        app.acquire_token_silent.assert_not_called()

    def test_oauth_error_details_are_not_exposed(self):
        msal = Mock()
        msal.PublicClientApplication.return_value.acquire_token_interactive.return_value = {
            "error": "secret-provider-response", "error_description": "token"}
        with patch.dict(sys.modules, {"msal": msal}):
            with self.assertRaises(OneDriveConfigurationError) as error:
                OneDriveAuth(Mock(), client_id="id").connect()
        self.assertNotIn("secret", str(error.exception))

    def test_unencrypted_cache_is_rejected(self):
        extension = Mock()
        extension.build_encrypted_persistence.return_value.is_encrypted = False
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {"msal_extensions": extension}):
            with self.assertRaises(OneDriveConfigurationError):
                OneDriveTokenStore(Path(directory) / "cache.bin").create_cache()
        extension.PersistedTokenCache.assert_not_called()

    def test_protected_cache_uses_locked_library_cache(self):
        extension = Mock()
        extension.build_encrypted_persistence.return_value.is_encrypted = True
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, {"msal_extensions": extension}):
            OneDriveTokenStore(Path(directory) / "cache.bin").create_cache()
        extension.PersistedTokenCache.assert_called_once_with(extension.build_encrypted_persistence.return_value)
