# Juliette FakeVoice API

OpenAI-compatible adapter for the Kasane Teto GPT-SoVITS project Yeyito777/teto-tts.

It exposes GET /v1/models and POST /v1/audio/speech. The adapter forwards requests to the Teto project's own POST /tts API. It does not run the model itself.

## Selected Teto model

The selected upstream project is Teto TTS by Yeyito777, fine-tuned with GPT-SoVITS v2ProPlus. Its repository documents Teto-specific GPT and SoVITS checkpoints, three reference clips, and a built-in HTTP API at POST /tts. The API accepts JSON containing text and language and returns WAV audio.

The upstream README reports CPU support, around 10 GB disk use, and roughly 2x real-time generation. These are author-reported figures, not a guarantee for every host.

The upstream repository states that its project is MIT-licensed. The model is a fan work; character and voice rights remain with their respective owners.

## Deploy the Teto inference backend

The inference backend must be deployed separately on a persistent Linux host with Python 3.10+ and about 10 GB free disk. CPU mode is documented; generation may be slower than a GPU host.

    git clone https://github.com/Yeyito777/teto-tts.git
    cd teto-tts
    ./setup.sh
    ./tts --serve --port 5000

The setup downloads the GPT-SoVITS engine, pretrained models, Teto checkpoints, and reference audio. Keep this service private or protect it with network-level access control. The upstream API itself does not provide authentication.

Set the backend URL as TETO_TTS_URL on the adapter, without the trailing /tts path.

## Deploy this adapter

Deploy this directory as a Docker web service. The included Render blueprint configures the adapter. Set these environment variables:

- FAKEVOICE_API_KEY: a long random secret.
- TETO_TTS_URL: base URL of the running Teto TTS backend, without /tts.
- TETO_TTS_LANGUAGE: ja, en, zh, ja_en, zh_en, or auto. Default: auto.
- TETO_TTS_TIMEOUT: request timeout in seconds. Default: 240.

The adapter is lightweight; actual synthesis happens on the separate Teto backend.

## Test

    curl -H "Authorization: Bearer YOUR_KEY" https://YOUR-ADAPTER/v1/models

    curl -X POST https://YOUR-ADAPTER/v1/audio/speech \
      -H "Authorization: Bearer YOUR_KEY" \
      -H "Content-Type: application/json" \
      -d '{"model":"kasane-teto-gpt-sovits","input":"こんにちは","response_format":"wav"}' \
      --output speech.wav

The speech endpoint currently returns WAV only and validates the WAV signature.

## Juliette configuration

Use the adapter's public base URL in the bot's FakeVoice URL setting. Set the same secret as TTS_API_KEY in Wispbyte. Do not put API keys in GitHub.

The Google Drive RVC checkpoint is unrelated: it is a voice-conversion model and is not used by this GPT-SoVITS TTS backend.

## License and attribution

The adapter code in this directory is maintained in this repository. The upstream Teto TTS project states that its code is MIT-licensed. Kasane Teto is a character by TWIN DRILL; this is an unofficial fan project and is not endorsed by the rights holders. Review the upstream repository's current license and asset terms before public or commercial deployment.
