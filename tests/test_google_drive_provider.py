import unittest
from unittest.mock import patch

from core.google_drive_provider import (
    GoogleDriveAmbiguousPathError,
    GoogleDriveProvider,
    GoogleDriveUnsupportedItemError,
)
from core.storage_provider import TransferPreconditionFailed
from models.storage_location import StorageLocation
from models.transfer_precondition import TransferPrecondition


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


class FakeFiles:
    def __init__(self, pages, folder_access=None):
        self.pages = pages
        self.folder_access = folder_access or {}
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        return FakeRequest(self.pages.get((kwargs["q"], kwargs.get("pageToken")), {}))

    def get(self, **kwargs):
        item_id = kwargs["fileId"]
        default = {
            "id": item_id,
            "mimeType": "application/vnd.google-apps.folder",
            "trashed": False,
            "capabilities": {"canListChildren": True},
        }
        return FakeRequest(self.folder_access.get(item_id, default))


class FakeService:
    def __init__(self, pages, folder_access=None):
        self.files_api = FakeFiles(pages, folder_access)

    def files(self):
        return self.files_api


class GoogleDriveProviderTests(unittest.TestCase):
    def provider_for(self, pages, folder_access=None):
        service = FakeService(pages, folder_access)
        return GoogleDriveProvider("root-id", "Selected", "user@example.test", service=service), service

    def test_scan_rejects_duplicate_siblings_including_folders(self):
        query = "'root-id' in parents and trashed=false"
        provider, _ = self.provider_for({
            (query, None): {"files": [
                {"id": "folder-1", "name": "Reports", "mimeType": "application/vnd.google-apps.folder"},
                {"id": "folder-2", "name": "Reports", "mimeType": "application/vnd.google-apps.folder"},
            ]}
        })

        with self.assertRaises(GoogleDriveAmbiguousPathError):
            provider.scan()

    def test_scan_rejects_duplicate_folders_split_across_pages(self):
        query = "'root-id' in parents and trashed=false"
        folder = lambda item_id: {
            "id": item_id, "name": "Reports", "mimeType": "application/vnd.google-apps.folder",
        }
        provider, _ = self.provider_for({
            (query, None): {"files": [folder("folder-1")], "nextPageToken": "next"},
            (query, "next"): {"files": [folder("folder-2")]},
        })

        with self.assertRaises(GoogleDriveAmbiguousPathError):
            provider.scan()

    def test_scan_rejects_case_insensitive_name_collisions_for_windows(self):
        query = "'root-id' in parents and trashed=false"
        provider, _ = self.provider_for({
            (query, None): {"files": [
                {"id": "one", "name": "Report.txt", "mimeType": "application/octet-stream"},
                {"id": "two", "name": "report.TXT", "mimeType": "application/octet-stream"},
            ]}
        })

        with self.assertRaises(GoogleDriveAmbiguousPathError):
            provider.scan()

    def test_scan_rejects_names_windows_cannot_create(self):
        query = "'root-id' in parents and trashed=false"
        for name in ("CON.txt", "COM\u00b9.log", "LPT\u00b3"):
            with self.subTest(name=name):
                provider, _ = self.provider_for({
                    (query, None): {"files": [{
                        "id": "reserved", "name": name,
                        "mimeType": "application/octet-stream",
                    }]}
                })

                with self.assertRaises(GoogleDriveUnsupportedItemError):
                    provider.scan()

    def test_scan_blocks_folders_when_the_user_cannot_list_contents(self):
        query = "'root-id' in parents and trashed=false"
        provider, _ = self.provider_for(
            {(query, None): {"files": []}},
            folder_access={"root-id": {
                "id": "root-id",
                "mimeType": "application/vnd.google-apps.folder",
                "trashed": False,
                "capabilities": {"canListChildren": False},
            }},
        )

        with self.assertRaisesRegex(GoogleDriveUnsupportedItemError, "cannot list every item"):
            provider.scan()

    def test_scan_rejects_google_workspace_documents_and_shortcuts(self):
        query = "'root-id' in parents and trashed=false"
        provider, _ = self.provider_for({
            (query, None): {"files": [{
                "id": "doc-id", "name": "Budget", "mimeType": "application/vnd.google-apps.spreadsheet",
            }]}
        })

        with self.assertRaises(GoogleDriveUnsupportedItemError):
            provider.scan()

    def test_scan_follows_pages_and_includes_shared_drive_items(self):
        query = "'root-id' in parents and trashed=false"
        first = {"id": "one", "name": "one.bin", "mimeType": "application/octet-stream", "size": "1", "version": "1"}
        second = {"id": "two", "name": "two.bin", "mimeType": "application/octet-stream", "size": "2", "version": "2"}
        provider, service = self.provider_for({
            (query, None): {"files": [first], "nextPageToken": "next"},
            (query, "next"): {"files": [second]},
        })

        records = provider.scan()

        self.assertEqual(set(records), {"one.bin", "two.bin"})
        self.assertEqual(len(service.files_api.calls), 2)
        for call in service.files_api.calls:
            self.assertTrue(call["supportsAllDrives"])
            self.assertTrue(call["includeItemsFromAllDrives"])

    def test_download_materializes_and_verifies_reviewed_drive_content(self):
        import hashlib
        from unittest.mock import Mock

        content = b"reviewed Drive file"
        item = {
            "id": "file-id", "name": "report.txt",
            "mimeType": "application/octet-stream", "size": str(len(content)),
            "modifiedTime": "2026-01-01T00:00:00Z",
            "md5Checksum": hashlib.md5(content).hexdigest(), "version": "7",
        }
        provider, _ = self.provider_for({})
        record = provider._to_record(item, "report.txt")
        provider._records["report.txt"] = record
        provider._fetch_record = Mock(side_effect=[record, record])
        provider._verify_parent_chain = Mock()  # Metadata/checksum unit; ancestry has separate coverage.

        class DownloadFiles:
            def get_media(self, **_kwargs):
                return object()

        class DownloadService:
            def files(self):
                return DownloadFiles()

        provider._service = DownloadService()

        class FakeDownloader:
            def __init__(self, output, _request):
                self.output = output

            def next_chunk(self):
                self.output.write(content)
                return None, True

        precondition = TransferPrecondition(
            source_location=record.storage_location,
            source_metadata=record.metadata,
            destination_location=StorageLocation.local("C:/destination/report.txt"),
            destination_metadata=None,
        )

        with patch("googleapiclient.http.MediaIoBaseDownload", FakeDownloader):
            with provider.open_transfer_content("report.txt", precondition) as downloaded:
                self.assertEqual(downloaded.local_path.read_bytes(), content)
                self.assertEqual(downloaded.size, len(content))
                self.assertEqual(downloaded.comparison_metadata.version_id, "7")
                temporary_path = downloaded.local_path

        self.assertFalse(temporary_path.exists())
        self.assertEqual(provider._fetch_record.call_count, 2)

    def test_download_stops_before_transfer_when_reviewed_version_changed(self):
        from unittest.mock import Mock

        item = {
            "id": "file-id", "name": "report.txt",
            "mimeType": "application/octet-stream", "size": "4",
            "modifiedTime": "2026-01-01T00:00:00Z", "version": "7",
        }
        provider, service = self.provider_for({})
        reviewed = provider._to_record(item, "report.txt")
        changed = provider._to_record({**item, "version": "8"}, "report.txt")
        provider._records["report.txt"] = reviewed
        provider._fetch_record = Mock(return_value=changed)
        provider._verify_parent_chain = Mock()
        precondition = TransferPrecondition(
            source_location=reviewed.storage_location,
            source_metadata=reviewed.metadata,
            destination_location=StorageLocation.local("C:/destination/report.txt"),
            destination_metadata=None,
        )

        with self.assertRaises(TransferPreconditionFailed):
            with provider.open_transfer_content("report.txt", precondition):
                self.fail("Changed Drive content must not be yielded")

        self.assertEqual(provider._fetch_record.call_count, 1)
        self.assertEqual(service.files_api.calls, [])


if __name__ == "__main__":
    unittest.main()
