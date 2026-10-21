import json
import os
from pathlib import Path
import tempfile
import runpy
import unittest
from unittest.mock import Mock, patch

from utils import provider_config as config
from core.onedrive_auth import OneDriveAuth, OneDriveConfigurationError


class ProviderConfigTests(unittest.TestCase):
    def test_frozen_onedrive_identity_needs_no_user_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "provider_config.json").write_text(json.dumps({
                "onedrive_client_id": "11111111-1111-1111-1111-111111111111",
                "onedrive_tenant": "consumers"}))
            with patch.dict(os.environ, {}, clear=True), \
                    patch.object(config.sys, "frozen", True, create=True), \
                    patch.object(config.sys, "_MEIPASS", directory, create=True):
                auth = OneDriveAuth(Mock())
                self.assertEqual(auth.client_id, "11111111-1111-1111-1111-111111111111")
                self.assertEqual(auth.tenant, "consumers")
                self.assertIsNone(auth._app)

    def test_developer_and_constructor_overrides(self):
        with patch.dict(os.environ, {config.ONEDRIVE_CLIENT_ID_ENV: "test-environment"}):
            self.assertEqual(config.get_onedrive_client_id(), "test-environment")
            self.assertEqual(OneDriveAuth(Mock(), client_id="explicit").client_id, "explicit")

    def test_invalid_or_missing_file_stops_auth_initialization(self):
        with tempfile.TemporaryDirectory() as directory:
            for content in (None, "{", "[]", '{"onedrive_client_id":123}'):
                path = Path(directory, "provider_config.json")
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_text(content)
                with patch.dict(os.environ, {}, clear=True), \
                        patch.object(config.sys, "frozen", True, create=True), \
                        patch.object(config.sys, "_MEIPASS", directory, create=True):
                    with self.assertRaises(OneDriveConfigurationError):
                        OneDriveAuth(Mock())

    def test_cloud_build_rejects_missing_invalid_ids_and_unsupported_providers(self):
        for client in ("", "placeholder", "00000000-0000-0000-0000-000000000000"):
            with self.subTest(client=client), self.assertRaises(ValueError):
                config.public_build_configuration({"TRACESYNC_BUILD_PROVIDERS": "onedrive",
                    config.ONEDRIVE_CLIENT_ID_ENV: client})
        with self.assertRaises(ValueError):
            config.public_build_configuration({"TRACESYNC_BUILD_PROVIDERS": "google"})
        with self.assertRaises(ValueError):
            config.public_build_configuration({"TRACESYNC_BUILD_PROVIDERS": "onedrive",
                config.ONEDRIVE_CLIENT_ID_ENV: "11111111-1111-1111-1111-111111111111",
                config.ONEDRIVE_TENANT_ENV: "organizations"})

    def test_build_emits_public_allowlist_only(self):
        result = config.public_build_configuration({"TRACESYNC_BUILD_PROVIDERS": "onedrive",
            config.ONEDRIVE_CLIENT_ID_ENV: "11111111-1111-1111-1111-111111111111",
            "ACCESS_TOKEN": "synthetic-do-not-bundle", "CLIENT_SECRET": "synthetic-secret"})
        self.assertEqual(result, {"onedrive_client_id": "11111111-1111-1111-1111-111111111111",
                                  "onedrive_tenant": "consumers"})
        self.assertEqual(config.public_build_configuration({"CLIENT_SECRET": "unused"}), {})

    def test_spec_embeds_configuration_in_disposable_workpath_without_building(self):
        from PyInstaller.config import CONF
        with tempfile.TemporaryDirectory() as directory:
            analysis = Mock()
            environment = {"TRACESYNC_BUILD_PROVIDERS": "onedrive",
                config.ONEDRIVE_CLIENT_ID_ENV: "11111111-1111-1111-1111-111111111111"}
            root = Path(__file__).resolve().parents[1]
            with patch.dict(CONF, {"workpath": directory}), patch.dict(os.environ, environment, clear=True):
                runpy.run_path(str(root / "TraceSync.spec"), init_globals={
                    "SPECPATH": str(root), "Analysis": analysis, "PYZ": Mock(), "EXE": Mock()})
            bundled = Path(directory) / "provider_config.json"
            self.assertEqual(json.loads(bundled.read_text()), {
                "onedrive_client_id": environment[config.ONEDRIVE_CLIENT_ID_ENV], "onedrive_tenant": "consumers"})
            self.assertIn((str(bundled), "."), analysis.call_args.kwargs["datas"])
