import unittest

from ui.utils.formatting import format_bytes, format_file_type, format_timestamp


class FormattingTests(unittest.TestCase):
    def test_format_bytes_handles_common_sizes(self):
        self.assertEqual(format_bytes(10), "10 B")
        self.assertEqual(format_bytes(1536), "1.50 KB")
        self.assertEqual(format_bytes(1048576), "1.00 MB")

    def test_format_bytes_is_resilient(self):
        self.assertEqual(format_bytes(None), "—")
        self.assertEqual(format_bytes("bad"), "—")
        self.assertEqual(format_bytes(-1), "—")

    def test_format_timestamp_returns_human_readable(self):
        self.assertTrue("2026" in format_timestamp(1770782400))

    def test_format_timestamp_invalid_values(self):
        self.assertEqual(format_timestamp(None), "Not Available")
        self.assertEqual(format_timestamp("bad"), "Invalid timestamp")

    def test_format_file_type_from_path(self):
        self.assertIn("PDF", format_file_type("notes/report.PDF").upper())
        self.assertEqual(format_file_type(""), "Unknown")
