import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from utils import provider_config as config


class ProviderConfigTests(unittest.TestCase):
    def test_frozen_google_identity_and_developer_override(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "provider_config.json").write_text(json.dumps({"google_drive_client_id": "packaged-client"}), encoding="utf-8-sig")
            with patch.object(config.sys, "frozen", True, create=True), \
                    patch.object(config.sys, "_MEIPASS", directory, create=True), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(config.get_google_client_id(), "packaged-client")
                with patch.dict(os.environ, {config.GOOGLE_CLIENT_ID_ENV: "developer-client"}):
                    self.assertEqual(config.get_google_client_id(), "developer-client")

    def test_build_selects_only_reviewed_providers_and_public_fields(self):
        environment = {"TRACESYNC_BUILD_PROVIDERS": "onedrive,google_drive",
            config.ONEDRIVE_CLIENT_ID_ENV: "11111111-1111-1111-1111-111111111111",
            config.GOOGLE_CLIENT_ID_ENV: "1234567890-synthetic.apps.googleusercontent.com",
            "CLIENT_SECRET": "never-bundle", "ACCESS_TOKEN": "never-bundle"}
        self.assertEqual(set(config.public_build_configuration(environment)),
            {"onedrive_client_id", "onedrive_tenant", "google_drive_client_id"})
        self.assertEqual(config.public_build_configuration({}), {})
        for selection in ("dropbox", "sftp", "google_drive"):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                config.public_build_configuration({"TRACESYNC_BUILD_PROVIDERS": selection})

    def test_spec_includes_public_data_and_native_keyring_without_building(self):
        with tempfile.TemporaryDirectory() as directory:
            analysis = Mock()
            modules = {"PyInstaller": Mock(), "PyInstaller.config": SimpleNamespace(CONF={"workpath": directory})}
            environment = {"TRACESYNC_BUILD_PROVIDERS": "google_drive",
                config.GOOGLE_CLIENT_ID_ENV: "1234567890-synthetic.apps.googleusercontent.com"}
            root = Path(__file__).resolve().parents[1]
            with patch.dict(sys.modules, modules), patch.dict(os.environ, environment, clear=True):
                runpy.run_path(str(root / "TraceSync.spec"), init_globals={
                    "SPECPATH": str(root), "Analysis": analysis, "PYZ": Mock(), "EXE": Mock()})
            bundled = Path(directory, "provider_config.json")
            self.assertEqual(json.loads(bundled.read_text()), {"google_drive_client_id": environment[config.GOOGLE_CLIENT_ID_ENV]})
            self.assertIn((str(bundled), "."), analysis.call_args.kwargs["datas"])
            self.assertIn("keyring.backends.Windows", analysis.call_args.kwargs["hiddenimports"])
