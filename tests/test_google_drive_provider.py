import unittest
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen
from threading import Thread
from unittest.mock import patch

from core.google_drive_auth import _run_picker_flow, revoke_google_sign_in
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

    def test_folder_picker_listing_follows_pages(self):
        query = "'root-id' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        provider, _ = self.provider_for({
            (query, None): {"files": [{"id": "a", "name": "A"}], "nextPageToken": "next"},
            (query, "next"): {"files": [{"id": "b", "name": "B"}]},
        })

        self.assertEqual(provider.list_folders(), [
            {"id": "a", "name": "A"}, {"id": "b", "name": "B"},
        ])

    def test_picker_oauth_requests_narrow_scope_and_validates_loopback_state(self):
        class FakeFlow:
            def __init__(self):
                self.redirect_uri = None
                self.credentials = object()
                self.fetch_token_code = None
                self.authorization_parameters = None

            @classmethod
            def from_client_config(cls, config, scopes):
                instance = cls()
                instance.client_config = config
                instance.scopes = scopes
                return instance

            def authorization_url(self, **kwargs):
                self.authorization_parameters = kwargs
                query = urlencode({"state": "state-123", "redirect_uri": self.redirect_uri})
                return f"https://accounts.google.test/auth?{query}", "state-123"

            def fetch_token(self, *, code):
                self.fetch_token_code = code

        fake_flow = None
        callback_threads = []
        callback_errors = []

        def open_test_callback(auth_url, **_kwargs):
            query = parse_qs(urlsplit(auth_url).query)
            redirect = query["redirect_uri"][0]
            callback = f"{redirect}?" + urlencode({
                "code": "one-time-code",
                "state": query["state"][0],
                "picked_file_ids": "folder-id",
            })
            def request_callback():
                try:
                    with urlopen(callback, timeout=3) as response:
                        if response.status != 200:
                            callback_errors.append(f"Unexpected HTTP status: {response.status}")
                except Exception as error:
                    callback_errors.append(str(error))

            callback_thread = Thread(target=request_callback)
            callback_thread.start()
            callback_threads.append(callback_thread)
            return True

        original_factory = FakeFlow.from_client_config

        def tracking_factory(config, scopes):
            nonlocal fake_flow
            fake_flow = original_factory(config, scopes)
            return fake_flow

        with patch.object(FakeFlow, "from_client_config", side_effect=tracking_factory), \
                patch("core.google_drive_auth.webbrowser.open", side_effect=open_test_callback):
            credentials, picked_ids = _run_picker_flow(FakeFlow, "desktop-client-id")
        for callback_thread in callback_threads:
            callback_thread.join(timeout=4)
        self.assertEqual(callback_errors, [])

        self.assertIs(credentials, fake_flow.credentials)
        self.assertEqual(picked_ids, ["folder-id"])
        self.assertEqual(fake_flow.fetch_token_code, "one-time-code")
        self.assertEqual(fake_flow.scopes, ["https://www.googleapis.com/auth/drive.file"])
        self.assertEqual(fake_flow.authorization_parameters["trigger_onepick"], "true")
        self.assertEqual(fake_flow.authorization_parameters["allow_folder_selection"], "true")
        self.assertIn("select_account", fake_flow.authorization_parameters["prompt"])
        self.assertEqual(fake_flow.client_config["installed"]["client_secret"], "")

    def test_google_oauth_library_generates_pkce_for_picker_request(self):
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_config(
            {"installed": {
                "client_id": "desktop-client-id",
                "client_secret": "",
                "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }},
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        flow.redirect_uri = "http://127.0.0.1:49152/"

        authorization_url, _state = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            include_granted_scopes="false",
            trigger_onepick="true",
            allow_folder_selection="true",
        )

        parameters = parse_qs(urlsplit(authorization_url).query)
        self.assertEqual(parameters["scope"], ["https://www.googleapis.com/auth/drive.file"])
        self.assertEqual(parameters["trigger_onepick"], ["true"])
        self.assertEqual(parameters["allow_folder_selection"], ["true"])
        self.assertEqual(parameters["code_challenge_method"], ["S256"])
        self.assertTrue(parameters["code_challenge"][0])

    def test_disconnect_revokes_refresh_token_without_putting_it_in_url(self):
        class FakeTokenStore:
            deleted = False

            def get(self):
                return {"refresh_token": "private-refresh-token"}

            def delete(self):
                self.deleted = True

        class FakeResponse:
            status_code = 200

        token_store = FakeTokenStore()
        with patch("requests.post", return_value=FakeResponse()) as post:
            revoked = revoke_google_sign_in(token_store)

        self.assertTrue(revoked)
        self.assertTrue(token_store.deleted)
        self.assertEqual(post.call_args.kwargs["data"], {"token": "private-refresh-token"})
        self.assertNotIn("token", post.call_args.kwargs.get("params", {}))


if __name__ == "__main__":
    unittest.main()
