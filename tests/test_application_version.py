import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.application_version import UNKNOWN_VERSION, get_application_version


class ApplicationVersionTests(unittest.TestCase):
    def test_pyinstaller_spec_packages_version_resource(self):
        spec_path = Path(__file__).resolve().parents[1] / "TraceSync.spec"

        self.assertIn("('VERSION', '.')", spec_path.read_text(encoding="utf-8"))

    def test_reads_valid_version_file(self):
        with tempfile.TemporaryDirectory() as workspace:
            version_file = Path(workspace) / "VERSION"
            version_file.write_text("1.2.3\n", encoding="utf-8")

            self.assertEqual(get_application_version(version_file), "1.2.3")

    def test_missing_or_invalid_version_is_unknown(self):
        with tempfile.TemporaryDirectory() as workspace:
            missing_file = Path(workspace) / "missing"
            invalid_file = Path(workspace) / "VERSION"
            invalid_file.write_text("v0.9 development", encoding="utf-8")

            self.assertEqual(get_application_version(missing_file), UNKNOWN_VERSION)
            self.assertEqual(get_application_version(invalid_file), UNKNOWN_VERSION)

    def test_packaged_version_resource_is_preferred(self):
        with tempfile.TemporaryDirectory() as workspace:
            bundle_root = Path(workspace)
            (bundle_root / "VERSION").write_text("2.3.4", encoding="utf-8")

            with patch("utils.application_version.sys._MEIPASS", str(bundle_root), create=True):
                self.assertEqual(get_application_version(), "2.3.4")
