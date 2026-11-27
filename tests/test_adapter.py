import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapter import QuoquendoError, synthesize


class AdapterTests(unittest.TestCase):
    def test_requires_worker_and_data(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(QuoquendoError):
                synthesize("Hola")

    def test_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            synthesize("  ")

    def test_decodes_wav_response(self):
        wav = b"RIFF" + b"\\x00\\x00\\x00\\x00" + b"WAVE" + b"test"
        with tempfile.TemporaryDirectory() as folder:
            worker = Path(folder) / "worker"
            data = Path(folder) / "data"
            worker.touch()
            data.mkdir()
            response = {"ok": True, "wav_base64": base64.b64encode(wav).decode(), "error": None}
            class Result:
                returncode = 0
                stdout = json.dumps(response) + "\\n"
                stderr = ""
            with patch.dict(os.environ, {
                "QUOQUENDO_WORKER": str(worker),
                "QUOQUENDO_DATA": str(data),
            }), patch("adapter.subprocess.run", return_value=Result()):
                self.assertEqual(synthesize("Hola"), wav)


if __name__ == "__main__":
    unittest.main()
