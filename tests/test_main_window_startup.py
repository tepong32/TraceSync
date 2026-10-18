import gc
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ui.main_window import MainWindow


class SavedFolderStartupTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.local = self.root / "local"
        self.server = self.root / "server"
        self.local.mkdir()
        self.server.mkdir()
        self.settings_file = self.root / "settings.json"
        for context in (
            patch("utils.settings.SETTINGS_FILE", self.settings_file),
            patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "appdata")}),
        ):
            context.start()
            self.addCleanup(context.stop)

    def start(self, settings):
        self.settings_file.write_text(json.dumps(settings), encoding="utf-8")
        window = MainWindow()
        self.addCleanup(window.destroy)
        window.withdraw()
        return window

    def test_saved_paths_restore_without_trace_erasing_server(self):
        window = self.start({"local_folder": str(self.local), "server_folder": str(self.server)})
        self.assertEqual(window.local_var.get(), str(self.local))
        self.assertEqual(window.server_var.get(), str(self.server))
        self.assertEqual(window.settings["server_folder"], str(self.server))

    def test_absent_paths_start_blank_without_rewriting_configuration(self):
        window = self.start({})
        self.assertEqual(window.local_var.get(), "")
        self.assertEqual(window.server_var.get(), "")
        self.assertEqual(json.loads(self.settings_file.read_text()), {})

    def test_missing_or_non_directory_server_restores_but_comparison_blocks(self):
        for server in (self.root / "missing", self.root / "file.txt"):
            if server.suffix:
                server.write_text("untouched", encoding="utf-8")
            with self.subTest(server=server):
                window = self.start({"local_folder": str(self.local), "server_folder": str(server)})
                self.assertEqual(window.server_var.get(), str(server))
                with patch("ui.main_window.messagebox.showerror") as error:
                    window.compare_folders()
                error.assert_called_once()
                self.assertFalse(window.comparison_completed)

    def test_active_local_pair_restores_both_paths_and_selection(self):
        pair = {"name": "Saved", "local_folder": str(self.local), "server_folder": str(self.server)}
        window = self.start({"folder_pairs": [pair], "active_folder_pair": "Saved"})
        self.assertEqual(window.local_var.get(), pair["local_folder"])
        self.assertEqual(window.server_var.get(), pair["server_folder"])
        self.assertEqual(window.folder_pair_var.get(), "Saved")

    def test_browse_persists_both_paths_for_restart(self):
        window = self.start({})
        with patch("ui.main_window.filedialog.askdirectory", side_effect=[str(self.local), str(self.server)]):
            window.browse_local()
            window.browse_server()
        saved = json.loads(self.settings_file.read_text())
        restarted = self.start(saved)
        self.assertEqual(restarted.local_var.get(), str(self.local))
        self.assertEqual(restarted.server_var.get(), str(self.server))

    def test_server_restores_when_local_path_is_absent(self):
        window = self.start({"server_folder": str(self.server)})
        self.assertEqual(window.local_var.get(), "")
        self.assertEqual(window.server_var.get(), str(self.server))
