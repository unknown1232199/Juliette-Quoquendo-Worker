# Juliette FakeVoice API

A small OpenAI-compatible HTTP adapter for a separately hosted GPT-SoVITS API.
It exposes the exact endpoints used by Juliette:

- `GET /v1/models`
- `POST /v1/audio/speech`

It forwards speech requests to GPT-SoVITS `POST /tts`. This repository does
not contain GPT-SoVITS, a Teto checkpoint, or reference audio, and it does
not perform inference itself.

## Required GPT-SoVITS backend

You need a reachable GPT-SoVITS API server with its `/tts` endpoint enabled,
plus a reference audio file and its exact transcript configured on that
backend. The reference path must be readable by GPT-SoVITS, not by this proxy.

For a Kasane Teto voice, use audio/model assets you are authorized to use.
The selected RVC checkpoint in the Juliette bot is a separate voice-conversion
model; it is not a GPT-SoVITS TTS model and cannot replace the GPT-SoVITS
backend or its reference audio.

## Deploy

Deploy this directory as a Docker web service (for example, using the included
Render blueprint). Set these environment variables:

- `FAKEVOICE_API_KEY`: a long random secret. The bot sends it as Bearer auth
  using its existing `TTS_API_KEY` environment variable.
- `GPT_SOVITS_URL`: base URL of the running GPT-SoVITS API, without `/tts`.
- `GPT_SOVITS_REF_AUDIO_PATH`: absolute reference-audio path on the GPT-SoVITS
  host.
- `GPT_SOVITS_PROMPT_TEXT`: exact transcript of that reference audio.
- `GPT_SOVITS_PROMPT_LANG`: language of the reference transcript (default `ja`).
- `GPT_SOVITS_TEXT_LANG`: language of text sent by Juliette (default `auto`).

The proxy itself is lightweight. Actual speech generation happens on the
GPT-SoVITS backend, which may require a GPU and substantial model storage.
A free CPU web host is not sufficient to run GPT-SoVITS inference.

## Local checks

```sh
cd fakevoice-api
pip install -r requirements.txt
FAKEVOICE_API_KEY=dev-key uvicorn app:app --host 127.0.0.1 --port 8000
```

Check models:

```sh
curl -H "Authorization: Bearer dev-key" http://127.0.0.1:8000/v1/models
```

A speech request requires a configured and reachable GPT-SoVITS backend:

```sh
curl -X POST http://127.0.0.1:8000/v1/audio/speech \
  -H "Authorization: Bearer dev-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"kasane-teto-gpt-sovits","input":"こんにちは","response_format":"wav"}' \
  --output speech.wav
```

## Important

Do not put the API key in GitHub or in a public file. Configure it as a
secret in the hosting provider and set the same value as `TTS_API_KEY` in
Wispbyte. The base URL saved with `/fakevoice` is the deployed proxy URL,
not a Google Drive file URL.
