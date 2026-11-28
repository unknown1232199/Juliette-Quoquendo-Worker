# Juliette TTS — RVC library

Shared Google Drive folder:
https://drive.google.com/drive/folders/1zUEGXqS5aK8wVSuHiUsGJiVOqQHGQI7i

Folder ID: `1zUEGXqS5aK8wVSuHiUsGJiVOqQHGQI7i`

This directory defines a review-only catalog for RVC models. It is separate from the Quoquendo/Loquendo worker and from GPT-SoVITS Teto TTS.

## Drive layout

Keep RVC files under `RVC/`, grouped by voice or source. Keep a model's `.pth` and matching `.index` together when available. A matching index is optional for some models. Add a text note with author, source URL, RVC version, base version (v1/v2), and usage restrictions.

Do not put private files in a link-shared folder. Anyone with the link may be able to access it.

## Sync and catalog

Run on the separate machine that will host RVC inference, not in the Wispbyte Discord bot container:

```sh
python -m pip install gdown
python rvc-library/sync_drive.py --output ./voice-library
```

To rescan files already downloaded without contacting Drive:

```sh
python rvc-library/sync_drive.py --scan-only --output ./voice-library
```

The script scans `.pth` and `.index` files, calculates SHA-256 hashes, pairs files only when their names match unambiguously, and reports unmatched index files. It writes `catalog.json` with schema version 2.

Google Drive quotas and folder-download limits may interrupt large downloads. In that case, download the affected files manually into the output folder and run `--scan-only`.

## Safety and current limitations

- Every catalog entry is written with `enabled: false` and `status: needs_review`.
- A file extension and checksum do not prove that a model is safe, compatible, correctly paired, or legally usable.
- The catalog does not execute or load model files.
- This repository does not yet provide an RVC inference engine or a public `/v1/audio/speech` service.
- Do not load RVC checkpoints in the Discord bot process. The future bot integration should call a separately hosted inference API.
- The Google Drive catalog and this Quoquendo worker are separate components; this repository update does not modify Wispbyte or deploy a remote RVC server.

## Tests

```sh
python -m unittest discover -s rvc-library/tests -v
```
