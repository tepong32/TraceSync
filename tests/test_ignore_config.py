import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import utils.settings as settings_module
from core.ignore.ignore_loader import IgnoreLoader
from core.ignore.ignore_rule_engine import IgnoreRuleEngine
from core.storage_provider import ProviderCapability, StorageProvider
from core.sync_service import SyncService
from models.file_record import FileRecord


def _record(path: str, modified_time: float) -> FileRecord:
    return FileRecord(path, path, modified_time, 1)


class FakeStorageProvider(StorageProvider):
    def __init__(self, name, records=None, root: str = "."):
        self.name = name
        self.root = root
        self.records = records or {}
        self.failing_paths = set()

    @property
    def display_name(self):
        return self.name

    @property
    def capabilities(self):
        return frozenset({ProviderCapability.TIMESTAMPS})

    def scan(self):
        return self.records

    def get_record(self, relative_path):
        return self.records.get(relative_path)

    def destination_path(self, relative_path):
        return f"{self.name}/{relative_path}"

    def copy_from(self, source, relative_path):
        if relative_path in self.failing_paths:
            raise PermissionError(relative_path)
        self.records[relative_path] = source.get_record(relative_path)


class IgnoreConfigTests(unittest.TestCase):
    def test_normalize_ignore_patterns(self):
        raw_patterns = [
            "*.tmp",
            "  build/",
            "",
            "# comment",
            "reports/*.bak",
            "   ",
        ]
        normalized = settings_module._normalize_ignore_patterns(raw_patterns)
        self.assertEqual(normalized, ["*.tmp", "build/", "reports/*.bak"])

    def test_settings_load_normalizes_noisy_patterns(self):
        with tempfile.TemporaryDirectory() as workspace:
            settings_file = Path(workspace) / "settings.json"
            settings_file.write_text(
                json.dumps(
                    {
                        "ignore_patterns": [
                            " *.tmp ",
                            "",
                            "# note",
                            "logs/",
                        ],
                    },
                    indent=4,
                ),
                encoding="utf-8",
            )

            with patch.object(settings_module, "SETTINGS_FILE", settings_file):
                loaded = settings_module.SettingsService.load()

            self.assertEqual(
                loaded["ignore_patterns"],
                ["*.tmp", "logs/"],
            )

    def test_ignore_loader_composes_built_in_project_and_user_patterns(self):
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace)
            (root / ".tracesyncignore").write_text(
                "\n".join(["# ignore office temp files", "OfficeTemp/", "  *.bak  "]),
                encoding="utf-8",
            )

            loader = IgnoreLoader()
            rules = loader.load(
                root,
                user_ignore_patterns=["  *.tmp  ", "", "# ignore this", "custom-folder/"],
            )

            self.assertEqual(len(rules), len(IgnoreRuleEngine.BUILTIN_PATTERNS) + 4)
            self.assertEqual(rules[-1].pattern, "custom-folder/")
            self.assertEqual(rules[-1].source.value, "user")

    def test_compare_skips_user_patterns(self):
        local = FakeStorageProvider(
            "local",
            {
                "keep.txt": _record("local/keep.txt", 10),
                "ignore-me.tmp": _record("local/ignore-me.tmp", 20),
            },
            root="local",
        )
        server = FakeStorageProvider(
            "server",
            {"keep.txt": _record("server/keep.txt", 5)},
            root="server",
        )

        service = SyncService(local, server)
        results = service.compare(user_ignore_patterns=["*.tmp"])

        self.assertEqual([item.relative_path for item in results], ["keep.txt"])
