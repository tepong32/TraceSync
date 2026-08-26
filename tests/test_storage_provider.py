import tempfile
import unittest
from pathlib import Path

from core.local_storage_provider import LocalStorageProvider
from core.storage_provider import ProviderCapability
from models.file_record import FileRecord
from models.storage_location import StorageLocation
from models.sync_history import StorageEndpointSnapshot
from models.transfer_precondition import TransferPrecondition


class StorageLocationTests(unittest.TestCase):
    def test_provider_native_identity_round_trips_without_path_coercion(self):
        location = StorageLocation(
            provider_type="object-store",
            native_id="item_01JABC123",
            display_location="Finance/Reports/report.xlsx",
        )

        restored = StorageLocation.from_dict(location.to_dict())

        self.assertEqual(restored, location)
        self.assertEqual(restored.native_id, "item_01JABC123")
        self.assertEqual(str(restored), "Finance/Reports/report.xlsx")
        with self.assertRaises(TypeError):
            restored.as_local_path()

    def test_legacy_file_record_constructor_defaults_to_local_location(self):
        record = FileRecord("C:/Work/report.xlsx", "report.xlsx", 100.0, 42)

        self.assertEqual(record.absolute_path, "C:/Work/report.xlsx")
        self.assertEqual(record.display_location, "C:/Work/report.xlsx")
        self.assertEqual(record.storage_location.provider_type, "local")
        self.assertEqual(record.storage_location.native_id, "C:/Work/report.xlsx")

    def test_display_changes_do_not_change_provider_native_identity(self):
        first = StorageLocation("test-provider", "item-1", "Old/report.xlsx")
        renamed = StorageLocation("test-provider", "item-1", "New/report.xlsx")

        self.assertTrue(first.same_identity_as(renamed))


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

    def test_local_item_location_preserves_native_path_and_display_text(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            item_path = root / "Reports" / "report.xlsx"
            item_path.parent.mkdir()
            item_path.write_bytes(b"report")
            provider = LocalStorageProvider(workspace, "Local Folder")

            location = provider.location_for("Reports/report.xlsx")
            record = provider.get_record("Reports/report.xlsx")

            self.assertEqual(location.provider_type, "local")
            self.assertEqual(location.native_id, str(item_path.resolve()))
            self.assertEqual(location.display_location, str(item_path.resolve()))
            self.assertEqual(location.as_local_path(), item_path.resolve())
            self.assertEqual(provider.destination_path("Reports/report.xlsx"), str(item_path.resolve()))
            self.assertEqual(record.storage_location, location)
            self.assertTrue(record.metadata.timestamp_reliable)
            self.assertEqual(record.metadata.modified_time, item_path.stat().st_mtime)
            self.assertIsNone(record.metadata.content_hash)
            self.assertNotIn(ProviderCapability.HASHING, provider.capabilities)

    def test_local_provider_copy_remains_filesystem_compatible(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            source_root = root / "source"
            destination_root = root / "destination"
            source_root.mkdir()
            destination_root.mkdir()
            source_file = source_root / "nested" / "report.txt"
            source_file.parent.mkdir()
            source_file.write_text("local content", encoding="utf-8")
            source = LocalStorageProvider(str(source_root), "Source")
            destination = LocalStorageProvider(str(destination_root), "Destination")

            source_record = source.get_record("nested/report.txt")
            destination.transfer_from(
                source,
                "nested/report.txt",
                TransferPrecondition(
                    source_location=source_record.storage_location,
                    source_metadata=source_record.metadata,
                    destination_location=destination.location_for("nested/report.txt"),
                    destination_metadata=None,
                ),
            )

            copied = destination_root / "nested" / "report.txt"
            self.assertEqual(copied.read_text(encoding="utf-8"), "local content")
            self.assertEqual(
                destination.get_record("nested/report.txt").storage_location.as_local_path(),
                copied.resolve(),
            )
