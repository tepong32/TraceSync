import sys
import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.onedrive_auth import OneDriveAuth, OneDriveConfigurationError, OneDriveTokenStore, OneDriveReconnectRequired


class OneDriveAuthTests(unittest.TestCase):
    def test_real_msal_personal_cache_binds_consumer_realm_to_returned_home_identity(self):
        import msal
        tenant="9188040d-6c67-4c5b-b112-36a304b66dad"
        claims={"oid":"synthetic-local", "sub":"synthetic-sub", "tid":tenant}
        info=base64.urlsafe_b64encode(json.dumps({"uid":"synthetic-home", "utid":tenant}).encode()).decode().rstrip("=")
        response={"access_token":"synthetic-only", "client_info":info, "id_token_claims":claims}
        cache=msal.SerializableTokenCache()
        cache.add({"client_id":"synthetic-client", "token_endpoint":"https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
                   "scope":["User.Read"], "response":response})
        accounts=list(cache.search(cache.CredentialType.ACCOUNT))
        self.assertEqual(accounts[0]["realm"],"consumers")
        auth=OneDriveAuth(Mock(),client_id="synthetic-client")
        from types import SimpleNamespace
        # Avoid discovery/browser/network while exercising the real SDK's cache
        # grouping and public get_accounts representation, not a hand-made account.
        app=msal.PublicClientApplication.__new__(msal.PublicClientApplication)
        app.authority=SimpleNamespace(instance="login.microsoftonline.com")
        app.token_cache=cache
        app.acquire_token_interactive=Mock(return_value=response)
        auth._app=app
        auth.connect()
        self.assertEqual(auth.account_reference,"synthetic-home."+tenant)

    def test_returned_home_identity_disambiguates_accounts_with_same_local_identity(self):
        auth,app=self.make_auth()
        tenant="9188040d-6c67-4c5b-b112-36a304b66dad"
        info=base64.urlsafe_b64encode(json.dumps({"uid":"right","utid":tenant}).encode()).decode().rstrip("=")
        app.get_accounts.return_value=[
            {"home_account_id":"wrong."+tenant,"local_account_id":"local","realm":"consumers"},
            {"home_account_id":"right."+tenant,"local_account_id":"local","realm":"consumers"}]
        app.acquire_token_interactive.return_value={"access_token":"synthetic","client_info":info,
            "id_token_claims":{"oid":"local","tid":tenant}}
        auth.connect()
        self.assertEqual(auth.account_reference,"right."+tenant)

    def test_invalid_client_info_never_falls_back_to_first_cached_account(self):
        auth,app=self.make_auth()
        for info in ("invalid-base64", "", {}, base64.urlsafe_b64encode(b'{"uid":12,"utid":"tenant"}').decode()):
            with self.subTest(info=type(info).__name__):
                app.acquire_token_interactive.return_value={"access_token":"synthetic-private", "client_info":info,
                    "id_token_claims":{"oid":"local-saved","tid":"tenant"}}
                with self.assertRaises(OneDriveConfigurationError) as caught:
                    auth.connect()
                self.assertNotIn("synthetic-private",str(caught.exception))
                self.assertEqual(auth.account_reference,"")

    def test_consumer_realm_alias_is_not_accepted_for_an_arbitrary_tenant(self):
        auth,app=self.make_auth()
        app.get_accounts.return_value=[{"home_account_id":"wrong","local_account_id":"local","realm":"consumers"}]
        app.acquire_token_interactive.return_value={"access_token":"synthetic",
            "id_token_claims":{"oid":"local","tid":"different-tenant"}}
        auth.connect()
        self.assertEqual(auth.account_reference,"")

    def make_auth(self):
        auth = OneDriveAuth(Mock(), client_id="test-client")
        app = Mock()
        app.get_accounts.return_value = [
            {"home_account_id": "other", "local_account_id": "local-other", "realm": "tenant"},
            {"home_account_id": "saved", "local_account_id": "local-saved", "realm": "tenant"},
        ]
        auth._app = app
        return auth, app

    def test_silent_renewal_selects_saved_account_not_first_cached_account(self):
        auth, app = self.make_auth()
        app.acquire_token_silent.return_value = {"access_token": "renewed"}
        with patch.dict(sys.modules, {"msal": Mock()}):
            self.assertEqual(auth.acquire_for_account("saved")[0], "renewed")
        self.assertEqual(app.acquire_token_silent.call_args.kwargs["account"]["home_account_id"], "saved")
        app.acquire_token_interactive.assert_not_called()

    def test_missing_ambiguous_or_expired_cache_requires_reconnect_without_browser(self):
        for case in ("missing", "ambiguous", "expired", "network"):
            with self.subTest(case=case):
                auth, app = self.make_auth()
                if case == "missing":
                    app.get_accounts.return_value = []
                elif case == "ambiguous":
                    app.get_accounts.return_value = [{"home_account_id": "saved"}] * 2
                elif case == "network":
                    app.acquire_token_silent.side_effect = RuntimeError("secret-token")
                else:
                    app.acquire_token_silent.return_value = None
                with patch.dict(sys.modules, {"msal": Mock()}):
                    with self.assertRaises(OneDriveReconnectRequired) as error:
                        auth.acquire_for_account("saved")
                self.assertNotIn("secret-token", str(error.exception))
                app.acquire_token_interactive.assert_not_called()

    def test_explicit_reconnect_rejects_different_account(self):
        auth, app = self.make_auth()
        app.acquire_token_interactive.return_value = {
            "access_token": "other-token", "id_token_claims": {"oid": "local-other", "tid": "tenant"}}
        with patch.dict(sys.modules, {"msal": Mock()}):
            with self.assertRaises(OneDriveReconnectRequired):
                auth.acquire_for_account("saved", interactive=True)
        self.assertEqual(auth.account_reference, "")

    def test_interactive_result_binds_exact_cache_identity(self):
        auth, app = self.make_auth()
        app.acquire_token_interactive.return_value = {
            "access_token": "saved-token", "id_token_claims": {"oid": "local-saved", "tid": "tenant"}}
        with patch.dict(sys.modules, {"msal": Mock()}):
            auth.acquire_for_account("saved", interactive=True)
        self.assertEqual(auth.account_reference, "saved")

    def test_disconnect_removes_only_matching_account_and_preserves_cache_file(self):
        auth, app = self.make_auth()
        with patch.dict(sys.modules, {"msal": Mock()}):
            auth.forget_account("saved")
        app.remove_account.assert_called_once_with(app.get_accounts.return_value[1])
        auth.token_store.delete.assert_not_called()

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
        self.assertEqual(app.acquire_token_interactive.call_args.kwargs["timeout"], 300)
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
