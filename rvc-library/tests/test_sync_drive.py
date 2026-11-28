import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "sync_drive.py"
SPEC = importlib.util.spec_from_file_location("sync_drive", SCRIPT)
sync_drive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_drive)


class CatalogTests(unittest.TestCase):
    def test_pairs_matching_model_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Kasane Teto").mkdir()
            (root / "Kasane Teto" / "Teto.pth").write_bytes(b"model")
            (root / "Kasane Teto" / "Teto.index").write_bytes(b"index")
            catalog = sync_drive.scan_library(root, "https://drive.google.com/drive/folders/example")
            self.assertEqual(len(catalog["models"]), 1)
            self.assertEqual(catalog["models"][0]["index_file"], "Kasane Teto/Teto.index")
            self.assertFalse(catalog["models"][0]["enabled"])

    def test_unmatched_index_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "voice.index").write_bytes(b"index")
            catalog = sync_drive.scan_library(root, "https://drive.google.com/drive/folders/example")
            self.assertEqual(catalog["unmatched_index_files"], ["voice.index"])
            self.assertIn("No .pth model files found.", catalog["warnings"])

    def test_rejects_non_drive_urls(self):
        self.assertFalse(sync_drive.safe_folder_url("https://example.com/folder/123"))


if __name__ == "__main__":
    unittest.main()
