import tempfile
import unittest
from pathlib import Path

from core.local_storage_provider import LocalStorageProvider
from models.sync_history import StorageEndpointSnapshot


class LocalStorageProviderEndpointTests(unittest.TestCase):
    def test_endpoint_snapshot_contains_only_safe_location_fields(self):
        with tempfile.TemporaryDirectory() as workspace:
            provider = LocalStorageProvider(workspace, "Local Folder")

            snapshot = provider.describe_endpoint()

            self.assertEqual(snapshot.provider_type, "local")
            self.assertEqual(snapshot.display_name, "Local Folder")
            self.assertEqual(snapshot.locator, str(Path(workspace).resolve()))
            self.assertEqual(
                set(snapshot.to_dict()),
                {"provider_type", "display_name", "locator"},
            )

    def test_endpoint_snapshot_rejects_uri_credentials(self):
        with self.assertRaises(ValueError):
            StorageEndpointSnapshot(
                "remote",
                "Remote Folder",
                "https://user:secret@example.test/folder",
            )
