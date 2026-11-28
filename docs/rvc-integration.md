# Juliette TTS → Juliette-RVC-Engine integration

## Flow

1. The selected TTS provider (Quoquendo, Loquendo, or another provider) generates a WAV from the user's text.
2. The bot passes those WAV bytes to `rvc_stage.process_tts_audio()`.
3. The stage checks that RVC is enabled and that the selected model is enabled in the local `rvc_models.json`.
4. `rvc_adapter.py` sends a multipart request to the separate Juliette-RVC-Engine service:
   - `POST /v1/rvc/convert`
   - `X-API-Key: ...`
   - `model_id`, `file`, `semitone_shift`, and `retrieval_blend`
5. The engine returns converted WAV bytes, which the bot plays in Discord.

The user's input remains text. WAV is only an internal intermediate result between TTS and RVC.

## Environment

Set these values in the bot runtime only after the inference service is deployed:

- `JULIETTE_RVC_URL`: HTTPS base URL of Juliette-RVC-Engine (without the API route).
- `JULIETTE_RVC_API_KEY`: same API key configured in the engine.

Never commit the API key to GitHub. The engine has its own model catalog and requires the selected model to be active there. The worker's local catalog is a second safety gate; keep a model disabled until the remote engine has the corresponding model and a real conversion test succeeds.

## Bot hook

The actual Discord Cog source is not stored in this repository. In the bot repository, import `rvc_stage` and call it once on every successful WAV return inside the common TTS synthesis method. That shared hook covers all commands and automatic reading paths that call the same synthesis method.

Example:

```python
import rvc_stage

async def process_tts_audio(self, audio: bytes) -> bytes:
    return await rvc_stage.process_tts_audio(audio, self.config)
```

Then route each successful generated WAV through `await self.process_tts_audio(audio)` before returning it to Discord playback.

## Safety and fallback

- No RVC inference runs inside the Wispbyte bot process.
- The RVC stage is off by default.
- A missing/disabled local model is an explicit configuration error.
- With `rvc_fallback: true`, transient service failures return the original TTS WAV.
- With `rvc_fallback: false`, conversion errors are raised.
- This repository's tests mock the HTTP response. They verify the client contract, not real model inference or voice quality.
