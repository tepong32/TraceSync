from pathlib import Path
import os
import shutil
import tempfile
import unittest

from core.backup_service import BackupService, BackupCreationError
from core.backup_store import JsonBackupStore
from core.onedrive_provider import OneDriveProvider
from core.storage_provider import ConditionalTransferUnsupported, ProviderCapability
from tests.test_onedrive_transfer import Graph, item


class OneDriveBackupContentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.graph=Graph();self.graph.files['saved.txt']=item('saved.txt',b'remote')
        self.graph.download=b'remote'
        self.provider=OneDriveProvider('drive','root','Synthetic',lambda:'synthetic-token',self.graph)
        self.backups=BackupService(JsonBackupStore(self.root/'backups'))

    def test_verified_remote_bytes_are_durable_locally_without_enabling_overwrite(self):
        with self.provider.open_backup_content('saved.txt') as content:
            self.assertEqual(content.materialized_modified_time,content.local_path.stat().st_mtime)
            self.assertEqual(content.comparison_metadata.modified_time,self.provider.get_record('saved.txt').modified_time)
        record=self.backups.create_backup(self.provider,'saved.txt','11111111-1111-1111-1111-111111111111')
        stored=self.backups.store.get(record.backup_id)
        self.assertEqual(stored.content_path.read_bytes(),b'remote')
        self.assertTrue(self.provider.create_only)
        self.assertNotIn(ProviderCapability.CONDITIONAL_TRANSFER,self.provider.capabilities)
        self.assertTrue(all(call[0] in ('GET','DOWNLOAD') for call in self.graph.calls))

    def test_source_changed_during_download_blocks_backup(self):
        self.graph.on_download=lambda:self.graph.files['saved.txt'].update(eTag='changed')
        with self.assertRaises(BackupCreationError):
            self.backups.create_backup(self.provider,'saved.txt','11111111-1111-1111-1111-111111111111')
        self.assertEqual(list((self.root/'backups/records').glob('*.json')),[])

    def test_wrong_download_size_blocks_backup_and_does_not_mutate_cloud(self):
        self.graph.download=b'partial'
        with self.assertRaises(BackupCreationError):
            self.backups.create_backup(self.provider,'saved.txt','11111111-1111-1111-1111-111111111111')
        self.assertTrue(all(call[0] in ('GET','DOWNLOAD') for call in self.graph.calls))

    @unittest.skipUnless(os.name=='nt','Windows sharing/cleanup behavior')
    def test_locked_temporary_content_cleanup_does_not_report_a_false_transfer_failure(self):
        handle=None;directory=None
        try:
            with self.provider.open_backup_content('saved.txt') as content:
                directory=content.local_path.parent
                handle=content.local_path.open('rb')
                self.assertEqual(handle.read(),b'remote')
        finally:
            if handle is not None:
                handle.close()
            if directory is not None:
                resolved=directory.resolve()
                self.assertEqual(resolved.parent,Path(tempfile.gettempdir()).resolve())
                self.assertTrue(resolved.name.startswith('tracesync-onedrive-'))
                shutil.rmtree(resolved,ignore_errors=True)
