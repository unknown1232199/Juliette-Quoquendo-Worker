# Juliette TTS — RVC library

Shared Google Drive folder:
https://drive.google.com/drive/folders/1zUEGXqS5aK8wVSuHiUsGJiVOqQHGQI7i

Folder ID: `1zUEGXqS5aK8wVSuHiUsGJiVOqQHGQI7i`

This directory defines the RVC model library for Juliette. It is deliberately separate from the Quoquendo/Loquendo worker and from the GPT-SoVITS Teto TTS backend.

## Drive layout

Organize files in Drive by voice/model, for example:

```
Juliette TTS/
  RVC/
    Kasane Teto/
    Hatsune Miku/
    Other Vocaloids/
    Anime/
    Other/
  GPT-SoVITS/
```

For an RVC model, keep the original `.pth` file and its matching `.index` file together when one exists. Keep a text note with the author, source URL, model version, base version (v1/v2), and any usage restrictions. Do not rename files until their pairing is confirmed.

## Download and scan

Run the helper on the machine that will host RVC inference, not on the Wispbyte bot container:

```sh
python -m pip install gdown
python rvc-library/sync_drive.py --output ./voice-library
```

The Drive folder must be shared so that anyone with the link can view/download it. The helper downloads the shared folder, scans for `.pth` and `.index` files, computes SHA-256 hashes, and writes `catalog.json` into the output directory.

Large folders may exceed Google Drive/gdown limits. If a download fails, use individual direct-download links for the affected model instead. This helper does not upload files to Drive, run RVC inference, or activate a model in Juliette.

## Safety and activation

Downloaded models are untrusted binary files. Keep them disabled until their source, architecture, and matching index are checked and an RVC inference backend is available. Never load a model into the Discord bot process itself. The bot should call a separate inference service.

The folder URL is public-link based. Anyone with the link may be able to access its contents, so do not put private files in it.
