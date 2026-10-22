import json
import io
import logging
import os
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from core.google_drive_auth import (GoogleDriveAuth, GoogleTokenStore, GoogleReconnectRequired,
    GoogleOAuthDiagnosticError, _with_oauth_diagnostics)
from core.google_drive_provider import GOOGLE_DRIVE_SCOPE, GoogleDriveConfigurationError


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.factory = Mock(return_value=self.store)
        self.api = Mock()
        self.api.about.return_value.get.return_value.execute.return_value = {
            "user": {"permissionId": "account-a", "emailAddress": "synthetic@example.invalid"}}
        self.auth = GoogleDriveAuth("synthetic.apps.googleusercontent.com", self.factory, lambda c: self.api)
        self.credentials = Mock(valid=True, refresh_token="synthetic")
        self.credentials.has_scopes.return_value = True
        self.credentials.to_json.return_value = '{"synthetic":true}'

    def test_real_sdk_transport_has_bounded_wait_without_network(self):
        from google.auth.credentials import AnonymousCredentials
        from google_auth_httplib2 import AuthorizedHttp
        auth = GoogleDriveAuth(self.auth.client_id, self.factory)
        with patch("googleapiclient.discovery.build", return_value=self.api) as build:
            connection = auth._connection(AnonymousCredentials())
        self.assertEqual(connection.account_id, "account-a")
        transport = build.call_args.kwargs["http"]
        self.assertIsInstance(transport, AuthorizedHttp)
        self.assertEqual(transport.http.timeout, 120)
        self.assertNotIn("credentials", build.call_args.kwargs)

    def test_connect_uses_standard_pkce_loopback_and_persists_verified_account(self):
        with patch("google_auth_oauthlib.flow.InstalledAppFlow") as flow:
            flow.from_client_config.return_value.run_local_server.return_value = self.credentials
            result = self.auth.connect()
            kwargs = flow.from_client_config.call_args.kwargs
            self.assertEqual(kwargs["scopes"], [GOOGLE_DRIVE_SCOPE])
            self.assertTrue(kwargs["autogenerate_code_verifier"])
            args = flow.from_client_config.return_value.run_local_server.call_args.kwargs
            self.assertEqual((args["host"], args["port"]), ("127.0.0.1", 0))
            self.assertNotIn("trigger_onepick", args)
        self.assertEqual(result.account_id, "account-a")
        self.factory.assert_called_once_with(self.auth.client_id, "account-a")
        self.store.set.assert_called_once()

    def test_callback_oauth_error_is_actionable_and_does_not_expose_callback_values(self):
        class Flow:
            def authorization_url(self, **kwargs):
                return "https://accounts.google.com/", "private-state-value"
            def fetch_token(self, **kwargs):
                raise AssertionError("token exchange must not run for callback error")
        flow = _with_oauth_diagnostics(Flow())
        flow.authorization_url()
        callback = "http://127.0.0.1:1234/?state=private-state-value&error=access_denied&error_description=private-description&code=private-code"
        with self.assertRaises(GoogleOAuthDiagnosticError) as caught:
            flow.fetch_token(authorization_response=callback)
        message = str(caught.exception)
        self.assertIn("canceled or permission was declined", message)
        for secret in ("private-state-value", "private-description", "private-code", callback):
            self.assertNotIn(secret, message)

    def test_invalid_callback_state_is_distinguished_and_redacted(self):
        class Flow:
            def authorization_url(self, **kwargs):
                return "https://accounts.google.com/", "expected-state"
            def fetch_token(self, **kwargs):
                raise AssertionError("token exchange must not run for invalid state")
        flow = _with_oauth_diagnostics(Flow())
        flow.authorization_url()
        with self.assertRaisesRegex(GoogleOAuthDiagnosticError, "invalid sign-in response"):
            flow.fetch_token(authorization_response="http://127.0.0.1/?state=attacker-state&code=private-code")

    def test_token_exchange_failure_is_distinguished_and_redacted(self):
        class Flow:
            def authorization_url(self, **kwargs):
                return "https://accounts.google.com/", "private-state"
            def fetch_token(self, **kwargs):
                raise RuntimeError("private-token-response private-client-secret")
        flow = _with_oauth_diagnostics(Flow())
        flow.authorization_url()
        with self.assertRaises(GoogleOAuthDiagnosticError) as caught:
            flow.fetch_token(authorization_response="http://127.0.0.1/?state=private-state&code=private-code")
        self.assertIn("reached token exchange", str(caught.exception))
        for secret in ("private-state", "private-code", "private-token-response", "private-client-secret"):
            self.assertNotIn(secret, str(caught.exception))

    def test_callback_timeout_and_local_server_failure_have_distinct_safe_messages(self):
        from google_auth_oauthlib.flow import WSGITimeoutError
        with patch("google_auth_oauthlib.flow.InstalledAppFlow") as flow:
            flow.from_client_config.return_value.run_local_server.side_effect = WSGITimeoutError("private-state")
            with self.assertRaises(GoogleOAuthDiagnosticError) as timeout:
                self.auth.connect()
            self.assertIn("No response returned", str(timeout.exception))
            self.assertNotIn("private-state", str(timeout.exception))
        with patch("google_auth_oauthlib.flow.InstalledAppFlow") as flow:
            flow.from_client_config.return_value.run_local_server.side_effect = OSError("private-callback-url")
            with self.assertRaises(GoogleOAuthDiagnosticError) as server:
                self.auth.connect()
            self.assertIn("local sign-in callback", str(server.exception))
            self.assertNotIn("private-callback-url", str(server.exception))

    def test_unexpected_local_exception_is_generic_and_redacted(self):
        with patch("google_auth_oauthlib.flow.InstalledAppFlow") as flow:
            flow.from_client_config.side_effect = RuntimeError("private-token-response")
            with self.assertRaises(GoogleOAuthDiagnosticError) as caught:
                self.auth.connect()
        self.assertIn("unexpected local error", str(caught.exception))
        self.assertNotIn("private-token-response", str(caught.exception))

    def test_reconnect_wrong_account_never_saves_credentials(self):
        with patch("google_auth_oauthlib.flow.InstalledAppFlow") as flow:
            flow.from_client_config.return_value.run_local_server.return_value = self.credentials
            with self.assertRaises(GoogleReconnectRequired):
                self.auth.connect(expected_account="different-account")
        self.store.set.assert_not_called()

    def test_missing_refresh_token_never_saves_an_unrenewable_connection(self):
        self.credentials.refresh_token=None
        with patch("google_auth_oauthlib.flow.InstalledAppFlow") as flow:
            flow.from_client_config.return_value.run_local_server.return_value=self.credentials
            with self.assertRaisesRegex(GoogleReconnectRequired,"renewable"):
                self.auth.connect()
        self.store.set.assert_not_called()

    def test_sdk_callback_urls_are_not_logged_even_when_info_logging_is_enabled(self):
        logger=logging.getLogger("google_auth_oauthlib.flow")
        stream=io.StringIO();handler=logging.StreamHandler(stream)
        level=logger.level;filters=list(logger.filters)
        logger.addHandler(handler);logger.setLevel(logging.INFO)
        def callback(**kwargs):
            logger.info("GET /?code=synthetic-private-authorization-code")
            return self.credentials
        try:
            with patch("google_auth_oauthlib.flow.InstalledAppFlow") as flow:
                flow.from_client_config.return_value.run_local_server.side_effect=callback
                self.auth.connect()
            self.assertEqual(stream.getvalue(),"")
            self.assertEqual(logger.filters,filters)
        finally:
            logger.removeHandler(handler);logger.setLevel(level)

    def test_sdk_produces_real_pkce_challenge_without_network(self):
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_config({"installed": {
            "client_id": self.auth.client_id, "client_secret": "",
            "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"}},
            scopes=[GOOGLE_DRIVE_SCOPE], autogenerate_code_verifier=True)
        flow.redirect_uri = "http://127.0.0.1:49152/"
        url, state = flow.authorization_url(access_type="offline")
        values = parse_qs(urlsplit(url).query)
        self.assertEqual(values["code_challenge_method"], ["S256"])
        self.assertTrue(values["code_challenge"][0])
        self.assertTrue(state)

    def test_restore_checks_application_scope_identity_before_saving(self):
        self.store.get.return_value = {"client_id": self.auth.client_id, "scopes": [GOOGLE_DRIVE_SCOPE]}
        with patch("google.oauth2.credentials.Credentials.from_authorized_user_info", return_value=self.credentials), \
                patch("webbrowser.open", side_effect=AssertionError("no implicit browser")):
            self.assertEqual(self.auth.acquire_for_account("account-a").account_id, "account-a")
            self.credentials.refresh.assert_not_called()
            with self.assertRaises(GoogleReconnectRequired):
                self.auth.acquire_for_account("different-account")

    def test_invalid_saved_auth_does_not_attempt_refresh_or_interaction(self):
        for data in (None, {"client_id": "other", "scopes": [GOOGLE_DRIVE_SCOPE]},
                     {"client_id": self.auth.client_id, "scopes": ["https://www.googleapis.com/auth/drive.file"]},
                     {"client_id": self.auth.client_id, "scopes": [GOOGLE_DRIVE_SCOPE], "token_uri": "https://attacker.invalid"}):
            self.store.get.return_value = data
            with patch("google.oauth2.credentials.Credentials.from_authorized_user_info") as load:
                with self.assertRaises(GoogleReconnectRequired):
                    self.auth.acquire_for_account("account-a")
                load.assert_not_called()

    def test_expired_credentials_refresh_uses_bounded_request_timeout(self):
        self.store.get.return_value = {
            "client_id": self.auth.client_id,
            "token_uri": "https://oauth2.googleapis.com/token",
            "scopes": [GOOGLE_DRIVE_SCOPE],
        }
        self.credentials.valid = False
        self.credentials.refresh.side_effect = lambda request: setattr(self.credentials, "valid", True)
        with patch("google.oauth2.credentials.Credentials.from_authorized_user_info", return_value=self.credentials), \
                patch("google.auth.transport.requests.Request") as request_factory:
            request_factory.return_value = object()
            self.auth.acquire_for_account("account-a")
        request_factory.assert_called_once_with(timeout=120)
        self.credentials.refresh.assert_called_once_with(request_factory.return_value)

    def test_token_storage_is_scoped_and_never_uses_global_keyring(self):
        a = GoogleTokenStore("client", "account-a")
        self.assertNotEqual(a.key, GoogleTokenStore("client", "account-b").key)
        self.assertNotEqual(a.key, GoogleTokenStore("other", "account-a").key)
        with patch("keyring.backends.Windows.WinVaultKeyring") as native, \
                patch("keyring.get_keyring", side_effect=AssertionError("no fallback")):
            native.return_value.get_password.return_value = '{"synthetic":true}'
            self.assertEqual(a.get(), {"synthetic": True})
            a.set('{"synthetic":true}')
            a.delete()
            native.return_value.set_password.assert_called_once()
            native.return_value.delete_password.assert_called_once()

    def test_storage_errors_are_sanitized_without_plaintext_fallback(self):
        store = GoogleTokenStore("client", "account-a")
        with patch.object(store, "_backend", side_effect=OSError("secret-token-response")):
            for action in (store.get, lambda: store.set("synthetic"), store.delete):
                with self.assertRaises(GoogleDriveConfigurationError) as caught:
                    action()
                self.assertNotIn("secret-token-response", str(caught.exception))

    def test_disconnect_removes_only_requested_account(self):
        self.auth.forget_account("account-a")
        self.factory.assert_called_once_with(self.auth.client_id, "account-a")
        self.store.delete.assert_called_once()

    @unittest.skipUnless(os.name == "nt", "Real Windows credential storage is required")
    def test_real_windows_backend_round_trip_with_disposable_synthetic_entry(self):
        run=str(uuid4())
        store=GoogleTokenStore("synthetic-test-client",run)
        store.SERVICE="TraceSync.Acceptance.Google."+run
        # A fresh service namespace and random account key: never enumerate or
        # query production entries, and never place actual tokens in the fixture.
        self.assertIsNone(store.get())
        try:
            store.set(json.dumps({"synthetic":True,"run":run}))
            self.assertEqual(store.get(),{"synthetic":True,"run":run})
            code = """import sys
from core.google_drive_auth import GoogleTokenStore
s=GoogleTokenStore('synthetic-test-client',sys.argv[1])
s.SERVICE='TraceSync.Acceptance.Google.'+sys.argv[1]
assert s.get()=={'synthetic':True,'run':sys.argv[1]}
print('PASS synthetic cross-process read')
"""
            child=subprocess.run([sys.executable,"-B","-c",code,run],capture_output=True,text=True,timeout=15)
            self.assertEqual(child.returncode,0,child.stderr)
            self.assertEqual(child.stdout.strip(),"PASS synthetic cross-process read")
        finally:
            store.delete()
        self.assertIsNone(store.get())
