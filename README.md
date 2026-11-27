# Juliette Quoquendo Worker

A small, headless JSON-lines worker that uses the pure-Rust `quoquendo`
library to generate WAV audio for Juliette. It does not use the desktop GUI,
ALSA, or Wine.

## Important voice-data note

This repository does not contain Loquendo voice recordings or installer
payloads. Quoquendo needs a complete LTTS7 data tree supplied separately.
Only use voice data you are legally entitled to use. Do not add proprietary
voice installers, recordings, or extracted voice data to this repository.

## Build

The GitHub Actions workflow builds a Linux x86_64 release binary and uploads
it as an artifact. You can also build locally:

```sh
cargo build --manifest-path worker/Cargo.toml --release
```

The worker source is in `worker/src/main.rs`.

## Protocol

The worker reads one JSON request per line from stdin and writes one JSON
response per line to stdout:

```json
{"data_dir":"/path/to/LTTS7/data","voice":"Jorge","text":"Hola, ¿cómo estás?"}
```

A successful response contains `ok: true` and a Base64-encoded WAV in
`wav_base64`. An error response contains `ok: false` and an `error`
message. The worker stays alive and accepts multiple requests.

## Python adapter

Copy `adapter.py` alongside the bot code. Set:

- `QUOQUENDO_WORKER`: absolute path to the compiled worker binary.
- `QUOQUENDO_DATA`: absolute path to the LTTS7 `data` directory.

Example:

```python
from adapter import synthesize

wav_bytes = synthesize("Hola desde Juliette", voice="Jorge")
```

The adapter uses only Python's standard library. It returns WAV bytes; the
Discord Cog can wrap them in `discord.FFmpegPCMAudio` or attach the WAV.

## Tests

```sh
python -m unittest discover -s tests -v
```

The adapter test suite uses a mocked worker response. It checks the protocol
and WAV container validation, not the actual TTS engine or voice files.

## Wispbyte deployment status

Nothing in this repository deploys itself to Wispbyte. Before deployment,
confirm the host architecture and glibc compatibility with the GitHub Actions
binary, upload the artifact, and test the worker with legally obtained voice
data. The current Wispbyte bot and its startup configuration are not changed
by this project.
