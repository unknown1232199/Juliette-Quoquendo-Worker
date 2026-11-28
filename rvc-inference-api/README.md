# Juliette RVC Inference API

Separate inference service for the existing Juliette bot adapter. It is not deployed to Wispbyte.

## Contract

- `POST /convert`
- Authorization: `Bearer JULIETTE_RVC_API_KEY`
- JSON: `model`, `input_format: "wav"`, `audio_base64`, `model_download_url`, `model_download_format: "drive-folder"`
- JSON response: `audio_base64`

The service downloads the shared Drive folder on first request, caches it persistently, locates a single unambiguous .pth and optional matching .index, and invokes the RVC Project CLI. It never enables a model in Juliette's catalog.

## Deploy

Use a persistent-volume Linux host. RVC inference needs substantially more disk, memory and CPU/GPU resources than the Wispbyte bot. Build this directory with Docker and mount a persistent volume at `/data`.

Set `JULIETTE_RVC_API_KEY` to a long random secret. Keep the service behind HTTPS. Do not expose it without authentication.

The Docker image installs the RVC Project package from its upstream Git repository. That project is under active development; verify its CLI flags and runtime dependencies on the target host before considering the deployment production-ready. CPU inference may be slow.

## Drive layout

The shared folder should contain the Teto model's .pth and optional .index, preferably inside a named subfolder. The service rejects ambiguous multiple-checkpoint folders instead of guessing. The JSON metadata is retained as library metadata but is not loaded as executable code.

## Safety

- Model files are untrusted inputs. Only use checkpoints from sources you trust and have permission to use.
- Downloads are capped by `RVC_MAX_DOWNLOAD_BYTES`.
- All model files remain in a persistent external cache.
- The service does not auto-enable anything in the Discord bot.
- Do not put secrets in GitHub.
