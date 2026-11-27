import base64
import json
import unittest
from unittest.mock import patch

import rvc_adapter


WAV = b"RIFF" + b"\x04\x00\x00\x00" + b"WAVE"


class FakeResponse:
    status = 200
    headers = type("Headers", (), {"get_content_type": lambda self: "application/json"})()

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class RVCAdapterTests(unittest.TestCase):
    def test_rejects_non_wav(self):
        with self.assertRaises(ValueError):
            rvc_adapter.convert_wav(b"not audio", "test", endpoint="https://example.test/convert")

    def test_requires_https(self):
        with self.assertRaises(rvc_adapter.RVCError):
            rvc_adapter.convert_wav(WAV, "test", endpoint="http://example.test/convert")

    def test_requires_endpoint(self):
        with patch.dict("os.environ", {"JULIETTE_RVC_URL": ""}):
            with self.assertRaises(rvc_adapter.RVCError):
                rvc_adapter.convert_wav(WAV, "test")

    @patch("urllib.request.urlopen")
    def test_returns_valid_converted_wav(self, urlopen):
        body = json.dumps({"audio_base64": base64.b64encode(WAV).decode()}).encode()
        urlopen.return_value = FakeResponse(body)
        self.assertEqual(
            rvc_adapter.convert_wav(WAV, "kasane-teto-synthv-rvc-v2",
                                    endpoint="https://rvc.example.test/convert"),
            WAV,
        )


if __name__ == "__main__":
    unittest.main()
