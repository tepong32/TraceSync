import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from acceptance import cache_diagnostic as diagnostic
from acceptance.cache_support import PREFIX, checked_root
from scripts.build_cache_acceptance import acceptance_spec


class CacheAcceptanceTests(unittest.TestCase):
    def root(self):
        path = Path(tempfile.gettempdir()) / (PREFIX + str(uuid4()))
        self.addCleanup(lambda: __import__("shutil").rmtree(path) if path.exists() else None)
        return path

    def test_fresh_directory_and_marker_required(self):
        root = self.root()
        self.assertEqual(checked_root(str(root), create=True), root)
        self.assertEqual(checked_root(str(root)), root)
        with self.assertRaises(FileExistsError):
            checked_root(str(root), create=True)
        (root / "acceptance-marker.txt").write_text("unrelated")
        with self.assertRaises(ValueError):
            checked_root(str(root))

    def test_rejects_unsafe_or_ambiguous_paths(self):
        for raw in ("", ".", "relative", "C:/", str(Path.home()),
                    str(Path(tempfile.gettempdir()) / (PREFIX + "not-a-uuid")),
                    str(self.root() / ".." / "escape")):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                checked_root(raw, create=True)

    def test_unowned_case_directory_is_not_adopted(self):
        root = checked_root(str(self.root()), create=True)
        (root / "write").mkdir()
        with self.assertRaises(FileExistsError):
            diagnostic.run_case(root, "write")

    def test_real_windows_cache_roundtrip_and_negative_cases(self):
        # Source-process evidence only; never label this frozen or standard-user acceptance.
        root = checked_root(str(self.root()), create=True)
        for case in diagnostic.CASES[:-1]:
            with self.subTest(case=case):
                self.assertIsInstance(diagnostic.run_case(root, case), str)

    def test_unexpected_error_is_sanitized(self):
        with patch.object(diagnostic, "parse_args", side_effect=OSError("SECRET-RAW-CACHE")), patch("sys.stdout", new_callable=io.StringIO) as out:
            self.assertEqual(diagnostic.main([]), 1)
        result = json.loads(out.getvalue())
        self.assertEqual(result["error"], "diagnostic_failed")
        self.assertNotIn("SECRET", out.getvalue())

    def test_missing_or_unknown_invocation_is_sanitized(self):
        for argv in ([], ["--secret-unknown"], ["--cache-acceptance", "--directory", "SECRET"]):
            with self.subTest(argv=argv), patch("sys.stdout", new_callable=io.StringIO) as out:
                self.assertEqual(diagnostic.main(argv), 1)
                self.assertNotIn("SECRET", out.getvalue())
                self.assertEqual(json.loads(out.getvalue())["error"], "invalid_invocation")

    def test_elevated_run_refuses_before_directory_or_cache(self):
        with patch.object(diagnostic, "windows_identity", return_value={"elevated": True, "integrity_rid": 12288}), patch.object(diagnostic, "checked_root") as root, patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(diagnostic.main(["--cache-acceptance", "--directory", str(self.root()), "--case", "write"]), 1)
        root.assert_not_called()

    def test_offline_guards_in_disposable_process(self):
        # Audit hooks cannot be removed; install in a child, never the suite process.
        code = """
import sys
import msal
from acceptance.cache_diagnostic import offline_audit, forbidden_auth, run_case
from acceptance.cache_support import checked_root
msal.PublicClientApplication=forbidden_auth
root=checked_root(sys.argv[1],create=True)
sys.addaudithook(offline_audit)
assert run_case(root,'offline')=='network_browser_auth_guards_verified'
"""
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.root())], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_main_cross_process_output_and_offline_initialization(self):
        root = self.root()
        code = """
import sys
from acceptance import cache_diagnostic as d
# Only simulate the integrity check for source regression; frozen runs use real tokens.
d.windows_identity=lambda: {'elevated':False,'integrity_rid':8192}
raise SystemExit(d.main(sys.argv[1:]))
"""
        for case in diagnostic.CASES:
            with self.subTest(case=case):
                result = subprocess.run([sys.executable, "-B", "-c", code, "--cache-acceptance",
                                         "--directory", str(root), "--case", case], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], "PASS")
                self.assertNotIn(diagnostic.SYNTHETIC_MARKER, result.stdout + result.stderr)

    def test_temporary_spec_changes_only_acceptance_configuration(self):
        repo = Path(__file__).resolve().parents[1]
        original = (repo / "TraceSync.spec").read_text()
        generated = acceptance_spec(original, repo)
        self.assertIn("TraceSync-Cache-Acceptance", generated)
        self.assertIn("cache_runtime_hook.py", generated)
        self.assertIn("console=True", generated)
        self.assertEqual((repo / "TraceSync.spec").read_text(), original)
        with self.assertRaises(ValueError):
            acceptance_spec(original.replace("runtime_hooks=[]", "runtime_hooks=['changed']"), repo)
