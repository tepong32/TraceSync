from dataclasses import replace
import unittest
from unittest.mock import Mock

from core.google_drive_provider import GoogleDriveProvider, GoogleDriveUnsupportedItemError
from core.storage_provider import TransferPreconditionFailed, ConditionalTransferUnsupported
from models.storage_location import StorageLocation
from models.transfer_precondition import TransferPrecondition
from tests.test_google_drive_provider import FakeService


class GoogleSafetyTests(unittest.TestCase):
    def test_repeated_empty_pages_fail_without_partial_records(self):
        q = "'root' in parents and trashed=false"
        api = FakeService({(q,None): {"files": [], "nextPageToken": "repeat"},
                           (q,"repeat"): {"files": [], "nextPageToken": "repeat"}})
        provider = GoogleDriveProvider("root", "Test", "synthetic", service=api)
        with self.assertRaises(GoogleDriveUnsupportedItemError):
            provider.scan()
        self.assertEqual(provider._records, {})
        self.assertEqual(provider._parents, {"": "root"})

    def test_parent_name_identity_and_type_changes_fail_even_with_same_version(self):
        original = {"id": "file-id", "name": "file.txt", "parents": ["root"],
            "mimeType": "application/octet-stream", "size": "4", "version": "1"}
        api = Mock()
        provider = GoogleDriveProvider("root", "Test", "synthetic", service=api)
        for change in ({"id":"other"}, {"name":"renamed.txt"}, {"parents":["outside"]},
                       {"mimeType":"application/vnd.google-apps.shortcut"}):
            with self.subTest(change=change):
                api.files.return_value.get.return_value.execute.return_value = dict(original,**change)
                with self.assertRaises(TransferPreconditionFailed):
                    provider._fetch_record("file-id", "file.txt")

    def test_reviewed_size_tampering_is_rejected_without_download(self):
        provider = GoogleDriveProvider("root", "Test", "synthetic", service=Mock())
        record = provider._to_record({"id":"file-id", "size":"4", "version":"1"}, "file.txt")
        provider._records = {"file.txt":record}
        provider._fetch_record = Mock(return_value=record)
        provider._verify_parent_chain = Mock()
        precondition = TransferPrecondition(record.storage_location, replace(record.metadata,size=99),
            StorageLocation.local("C:/disposable/file.txt"), None)
        with self.assertRaises(TransferPreconditionFailed):
            with provider.open_transfer_content("file.txt",precondition):
                self.fail("Forged metadata must not yield content")
        provider._service.files.assert_not_called()

    def test_root_identity_mismatch_and_upload_attempt_are_rejected(self):
        api = Mock()
        api.files.return_value.get.return_value.execute.return_value = {
            "id":"wrong", "mimeType":"application/vnd.google-apps.folder",
            "capabilities":{"canListChildren":True}}
        provider = GoogleDriveProvider("root", "Test", "synthetic", service=api)
        with self.assertRaises(GoogleDriveUnsupportedItemError):
            provider.scan()
        with self.assertRaises(ConditionalTransferUnsupported):
            provider.transfer_from(Mock(),"file.txt",Mock())

    def test_fresh_parent_chain_rejects_ancestor_replacement_and_movement(self):
        api=Mock();provider=GoogleDriveProvider("root","Test","synthetic",service=api)
        provider._parents={"":"root","child":"child-id"}
        root={"id":"root","name":"Test","mimeType":"application/vnd.google-apps.folder"}
        child={"id":"child-id","name":"child","parents":["root"],"mimeType":"application/vnd.google-apps.folder"}
        for change in ({"id":"replacement"},{"parents":["outside"]},{"name":"renamed"},{"trashed":True}):
            with self.subTest(change=change):
                api.files.return_value.get.return_value.execute.side_effect=[root,dict(child,**change)]
                with self.assertRaises(TransferPreconditionFailed):
                    provider._verify_parent_chain("child/file.txt")

    def test_selected_root_label_is_not_coerced_to_a_windows_child_name(self):
        api=Mock();provider=GoogleDriveProvider("root"," Selected root ","synthetic",service=api)
        api.files.return_value.get.return_value.execute.return_value={
            "id":"root","name":" Selected root ","mimeType":"application/vnd.google-apps.folder"}
        provider._verify_parent_chain("file.txt")
