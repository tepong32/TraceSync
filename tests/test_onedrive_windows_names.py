import unittest
from core.onedrive_provider import OneDriveProvider


class OneDriveWindowsNamesTests(unittest.TestCase):
    def test_device_aliases_and_suffix_variants_are_rejected_before_local_mapping(self):
        for name in ("CON.txt", "CON .txt", "CONIN$", "CONOUT$.log", "COM\u00b9.log", "LPT\u00b2", "COM\u00b3.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                OneDriveProvider._path("folder/" + name)
        self.assertEqual(OneDriveProvider._path("folder/ordinary.txt"),["folder","ordinary.txt"])
