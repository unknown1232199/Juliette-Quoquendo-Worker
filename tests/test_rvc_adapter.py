import os
import unittest
from unittest.mock import patch

import rvc_adapter


WAV = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVE" + b"\x00" * 36


class FakeHeaders(dict):
    pass


class FakeResponse:
    status = 200
    headers = FakeHeaders({"Content-Type": "audio/wav"})

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return WAV


class RVCAdapterTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "JULIETTE_RVC_URL": "https://rvc.example.test",
            "JULIETTE_RVC_API_KEY": "test-secret",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_rejects_non_wav(self):
        with self.assertRaises(ValueError):
            rvc_adapter.convert_wav(b"not audio", "test")

    def test_requires_https(self):
        with self.assertRaises(rvc_adapter.RVCError):
            rvc_adapter.convert_wav(WAV, "test", endpoint="http://rvc.example.test")

    def test_requires_api_key(self):
        with patch.dict(os.environ, {"JULIETTE_RVC_API_KEY": ""}):
            with self.assertRaisesRegex(rvc_adapter.RVCError, "API_KEY"):
                rvc_adapter.convert_wav(WAV, "test")

    @patch("urllib.request.urlopen")
    def test_posts_engine_multipart_contract(self, urlopen):
        urlopen.return_value = FakeResponse()
        self.assertEqual(
            rvc_adapter.convert_wav(WAV, "kasane-teto-synthv-rvc-v2"),
            WAV,
        )
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://rvc.example.test/v1/rvc/convert")
        self.assertEqual(request.get_header("X-api-key"), "test-secret")
        self.assertIn(b'name="model_id"', request.data)
        self.assertIn(b'kasane-teto-synthv-rvc-v2', request.data)
        self.assertIn(b'name="file"; filename="tts-input.wav"', request.data)

    def test_validates_conversion_options(self):
        with self.assertRaises(ValueError):
            rvc_adapter.convert_wav(WAV, "test", semitone_shift=25)
        with self.assertRaises(ValueError):
            rvc_adapter.convert_wav(WAV, "test", retrieval_blend=1.1)


if __name__ == "__main__":
    unittest.main()
