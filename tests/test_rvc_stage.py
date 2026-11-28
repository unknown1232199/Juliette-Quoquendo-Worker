import unittest
from unittest.mock import patch

import rvc_stage


WAV = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVE" + b"\x00" * 36
MODEL = "kasane-teto-synthv-rvc-v2"


class RVCStageTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_returns_original(self):
        self.assertIs(await rvc_stage.process_tts_audio(WAV, {"rvc_enabled": False}), WAV)

    async def test_no_model_returns_original(self):
        self.assertIs(await rvc_stage.process_tts_audio(WAV, {"rvc_enabled": True}), WAV)

    async def test_enabled_converts_wav(self):
        with patch.object(rvc_stage, "get_model", return_value={"id": MODEL, "enabled": True}), \
             patch.object(rvc_stage, "convert_wav", return_value=WAV) as convert:
            result = await rvc_stage.process_tts_audio(
                WAV, {"rvc_enabled": True, "rvc_model": MODEL}
            )
        self.assertEqual(result, WAV)
        convert.assert_called_once_with(WAV, MODEL)

    async def test_model_must_be_enabled_locally(self):
        with patch.object(rvc_stage, "get_model", return_value=None):
            with self.assertRaisesRegex(rvc_stage.RVCError, "missing or disabled"):
                await rvc_stage.process_tts_audio(
                    WAV, {"rvc_enabled": True, "rvc_model": MODEL, "rvc_fallback": True}
                )

    async def test_fallback_returns_original_on_service_error(self):
        with patch.object(rvc_stage, "get_model", return_value={"id": MODEL, "enabled": True}), \
             patch.object(rvc_stage, "convert_wav", side_effect=RuntimeError("offline")):
            result = await rvc_stage.process_tts_audio(
                WAV, {"rvc_enabled": True, "rvc_model": MODEL, "rvc_fallback": True}
            )
        self.assertEqual(result, WAV)

    async def test_disabled_fallback_propagates_error(self):
        with patch.object(rvc_stage, "get_model", return_value={"id": MODEL, "enabled": True}), \
             patch.object(rvc_stage, "convert_wav", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                await rvc_stage.process_tts_audio(
                    WAV, {"rvc_enabled": True, "rvc_model": MODEL, "rvc_fallback": False}
                )


if __name__ == "__main__":
    unittest.main()
