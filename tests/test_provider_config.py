import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import utils.provider_config as provider_config


class ProviderConfigTests(unittest.TestCase):
    def test_environment_value_overrides_packaged_config(self):
        with patch.dict(os.environ, {provider_config.GOOGLE_CLIENT_ID_ENV: "environment-client"}):
            self.assertEqual(provider_config.get_google_client_id(), "environment-client")

    def test_build_data_config_supplies_public_client_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "utils").mkdir()
            (root / "provider_config.json").write_text(
                json.dumps({"google_drive_client_id": "packaged-client"}),
                encoding="utf-8",
            )
            fake_module = root / "utils" / "provider_config.py"
            with (
                patch.object(provider_config, "__file__", str(fake_module)),
                patch.dict(os.environ, {provider_config.GOOGLE_CLIENT_ID_ENV: ""}),
                patch.object(provider_config.sys, "frozen", False, create=True),
            ):
                self.assertEqual(provider_config.get_google_client_id(), "packaged-client")


if __name__ == "__main__":
    unittest.main()
