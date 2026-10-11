import os
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from core.local_file_commit import publish_new_file
from core.local_storage_provider import LocalStorageProvider
from core.storage_provider import (
    ProviderCapability,
    StorageProvider,
    TransferPreconditionFailed,
    TransferPreconditionTarget,
)
from models.backup_content import BackupContent
from models.file_record import FileRecord
from models.storage_location import StorageLocation
from models.sync_history import StorageEndpointSnapshot
from models.transfer_precondition import TransferPrecondition


class MaterializedTransferSource(StorageProvider):
    """Test-only non-local source that supplies verified local materialization."""

    def __init__(self, content_path: Path) -> None:
        self.content_path = content_path
        stat = content_path.stat()
        self.record = FileRecord.from_location(
            StorageLocation("test-provider", "object-1", "Remote/report.txt"),
            "report.txt",
            stat.st_mtime,
            stat.st_size,
        )

    @property
    def display_name(self):
        return "Materialized Source"

    @property
    def capabilities(self):
        return frozenset({ProviderCapability.TIMESTAMPS})

    def describe_endpoint(self):
        return StorageEndpointSnapshot(
            "test-provider",
            self.display_name,
            "account/root",
        )

    def scan(self):
        return {"report.txt": self.record}

    def get_record(self, relative_path):
        return self.record if relative_path == "report.txt" else None

    def location_for(self, relative_path):
        return self.record.storage_location

    def open_transfer_content(self, relative_path, precondition):
        stat = self.content_path.stat()
        return nullcontext(
            BackupContent(
                local_path=self.content_path,
                size=stat.st_size,
                modified_time=stat.st_mtime,
                comparison_metadata=self.record.metadata,
            )
        )


class ConditionalLocalTransferTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        root = Path(self.workspace.name)
        self.source_root = root / "source"
        self.destination_root = root / "destination"
        self.source_root.mkdir()
        self.destination_root.mkdir()
        self.source = LocalStorageProvider(str(self.source_root), "Source")
        self.destination = LocalStorageProvider(
            str(self.destination_root),
            "Destination",
        )

    @staticmethod
    def write_version(path: Path, content: str, modified_time: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        os.utime(path, (modified_time, modified_time))

    def reviewed_precondition(self, relative_path: str) -> TransferPrecondition:
        source_record = self.source.get_record(relative_path)
        destination_record = self.destination.get_record(relative_path)
        return TransferPrecondition(
            source_location=source_record.storage_location,
            source_metadata=source_record.metadata,
            destination_location=self.destination.location_for(relative_path),
            destination_metadata=(
                destination_record.metadata if destination_record else None
            ),
        )

    def test_expected_source_and_absent_destination_succeed(self):
        relative_path = "reports/report.txt"
        self.write_version(self.source_root / relative_path, "reviewed", 200)
        precondition = self.reviewed_precondition(relative_path)

        self.destination.transfer_from(
            self.source,
            relative_path,
            precondition,
        )

        self.assertEqual(
            (self.destination_root / relative_path).read_text(encoding="utf-8"),
            "reviewed",
        )
        self.assertIn(
            ProviderCapability.CONDITIONAL_CREATE,
            self.destination.capabilities,
        )
        self.assertIn(
            ProviderCapability.CONDITIONAL_TRANSFER,
            self.destination.capabilities,
        )

    def test_local_destination_accepts_provider_materialized_source(self):
        materialized_path = Path(self.workspace.name) / "materialized.txt"
        self.write_version(materialized_path, "provider content", 200)
        source = MaterializedTransferSource(materialized_path)
        source_record = source.get_record("report.txt")
        precondition = TransferPrecondition(
            source_location=source_record.storage_location,
            source_metadata=source_record.metadata,
            destination_location=self.destination.location_for("report.txt"),
            destination_metadata=None,
        )

        self.destination.transfer_from(source, "report.txt", precondition)

        self.assertEqual(
            (self.destination_root / "report.txt").read_text(encoding="utf-8"),
            "provider content",
        )

    def test_changed_source_is_rejected(self):
        relative_path = "report.txt"
        source_path = self.source_root / relative_path
        self.write_version(source_path, "reviewed", 200)
        precondition = self.reviewed_precondition(relative_path)
        self.write_version(source_path, "changed source", 300)

        with self.assertRaises(TransferPreconditionFailed) as raised:
            self.destination.transfer_from(
                self.source,
                relative_path,
                precondition,
            )

        self.assertIs(raised.exception.target, TransferPreconditionTarget.SOURCE)
        self.assertFalse((self.destination_root / relative_path).exists())

    def test_changed_destination_is_rejected_without_overwrite(self):
        relative_path = "report.txt"
        source_path = self.source_root / relative_path
        destination_path = self.destination_root / relative_path
        self.write_version(source_path, "reviewed source", 200)
        self.write_version(destination_path, "reviewed destination", 100)
        precondition = self.reviewed_precondition(relative_path)
        self.write_version(destination_path, "external change", 300)

        with self.assertRaises(TransferPreconditionFailed) as raised:
            self.destination.transfer_from(
                self.source,
                relative_path,
                precondition,
            )

        self.assertIs(
            raised.exception.target,
            TransferPreconditionTarget.DESTINATION,
        )
        self.assertEqual(
            destination_path.read_text(encoding="utf-8"),
            "external change",
        )

    def test_expected_destination_absence_is_enforced(self):
        relative_path = "report.txt"
        source_path = self.source_root / relative_path
        destination_path = self.destination_root / relative_path
        self.write_version(source_path, "reviewed source", 200)
        precondition = self.reviewed_precondition(relative_path)
        self.write_version(destination_path, "new destination", 300)

        with self.assertRaises(TransferPreconditionFailed) as raised:
            self.destination.transfer_from(
                self.source,
                relative_path,
                precondition,
            )

        self.assertIs(
            raised.exception.target,
            TransferPreconditionTarget.DESTINATION,
        )
        self.assertEqual(
            destination_path.read_text(encoding="utf-8"),
            "new destination",
        )

    def test_file_created_after_final_validation_is_preserved(self):
        self._assert_late_destination_preserved(is_directory=False)

    def test_directory_created_after_final_validation_is_preserved(self):
        self._assert_late_destination_preserved(is_directory=True)

    def _assert_late_destination_preserved(self, *, is_directory):
        relative_path = "report.txt"
        self.write_version(self.source_root / relative_path, "reviewed source", 200)
        condition = self.reviewed_precondition(relative_path)
        destination_path = self.destination_root / relative_path
        validate = self.destination._verify_transfer_precondition
        validations = 0

        def validate_then_create(*args):
            nonlocal validations
            validate(*args)
            validations += 1
            if validations == 2:
                if is_directory:
                    destination_path.mkdir()
                else:
                    self.write_version(destination_path, "external edit", 300)

        with patch.object(
            self.destination, "_verify_transfer_precondition",
            side_effect=validate_then_create,
        ), patch("core.local_storage_provider.os.replace", wraps=os.replace) as replace:
            with self.assertRaises(TransferPreconditionFailed) as raised:
                self.destination.transfer_from(self.source, relative_path, condition)

        self.assertEqual(validations, 2)
        self.assertIs(raised.exception.target, TransferPreconditionTarget.DESTINATION)
        replace.assert_not_called()
        if is_directory:
            self.assertTrue(destination_path.is_dir())
        else:
            self.assertEqual(destination_path.read_text(encoding="utf-8"), "external edit")
        self.assertEqual(list(self.destination_root.iterdir()), [destination_path])

    def test_publication_failure_does_not_fall_back_to_overwrite(self):
        self.write_version(self.source_root / "report.txt", "reviewed", 200)
        condition = self.reviewed_precondition("report.txt")
        with patch(
            "core.local_storage_provider.publish_new_file",
            side_effect=PermissionError("publication denied"),
        ), patch("core.local_storage_provider.os.replace") as replace:
            with self.assertRaises(PermissionError):
                self.destination.transfer_from(self.source, "report.txt", condition)
        replace.assert_not_called()
        self.assertEqual(list(self.destination_root.iterdir()), [])

    def test_cleanup_error_does_not_hide_destination_collision(self):
        self.write_version(self.source_root / "report.txt", "reviewed", 200)
        condition = self.reviewed_precondition("report.txt")
        with patch(
            "core.local_storage_provider.publish_new_file",
            side_effect=FileExistsError("destination appeared"),
        ), patch.object(Path, "unlink", side_effect=PermissionError("cleanup denied")):
            with self.assertRaises(TransferPreconditionFailed):
                self.destination.transfer_from(self.source, "report.txt", condition)

    def test_reviewed_existing_destination_still_replaced(self):
        self.write_version(self.source_root / "report.txt", "reviewed source", 200)
        self.write_version(self.destination_root / "report.txt", "reviewed target", 100)
        condition = self.reviewed_precondition("report.txt")
        self.destination.transfer_from(self.source, "report.txt", condition)
        self.assertEqual(
            (self.destination_root / "report.txt").read_text(encoding="utf-8"),
            "reviewed source",
        )


class NewFilePublicationTests(unittest.TestCase):
    def test_link_publication_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            destination = Path(directory) / "destination"
            staged.write_bytes(b"staged content")
            destination.write_bytes(b"external content")
            with patch("core.local_file_commit.OS_NAME", "posix"):
                with self.assertRaises(FileExistsError):
                    publish_new_file(staged, destination)
            self.assertEqual(destination.read_bytes(), b"external content")
            self.assertEqual(staged.read_bytes(), b"staged content")

    def test_link_publication_exposes_complete_content(self):
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / "staged"
            destination = Path(directory) / "destination"
            staged.write_bytes(b"complete content")
            with patch("core.local_file_commit.OS_NAME", "posix"):
                publish_new_file(staged, destination)
            staged.unlink()
            self.assertEqual(destination.read_bytes(), b"complete content")

    def test_unsupported_link_operation_never_uses_rename_or_replace(self):
        with patch("core.local_file_commit.OS_NAME", "posix"), patch(
            "core.local_file_commit.os.link", side_effect=OSError("unsupported")
        ), patch("core.local_file_commit.os.rename") as rename, patch(
            "core.local_file_commit.os.replace"
        ) as replace:
            with self.assertRaises(OSError):
                publish_new_file(Path("staged"), Path("destination"))
        rename.assert_not_called()
        replace.assert_not_called()


if __name__ == "__main__":
    unittest.main()
