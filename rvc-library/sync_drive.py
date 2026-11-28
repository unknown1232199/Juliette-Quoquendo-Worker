#!/usr/bin/env python3
"""Download the public Juliette TTS Drive folder and build an RVC file catalog.

Run this on the RVC inference host, not in the Wispbyte Discord bot container.
Requires: python -m pip install gdown
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

FOLDER_URL = "https://drive.google.com/drive/folders/1zUEGXqS5aK8wVSuHiUsGJiVOqQHGQI7i"
MODEL_SUFFIXES = {".pth", ".index"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync and catalog Juliette TTS RVC files from Google Drive.")
    parser.add_argument("--folder-url", default=FOLDER_URL)
    parser.add_argument("--output", default="./voice-library")
    args = parser.parse_args()

    try:
        import gdown
    except ImportError:
        print("Missing dependency. Install it with: python -m pip install gdown", file=sys.stderr)
        return 2

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    downloaded = gdown.download_folder(
        url=args.folder_url,
        output=str(output),
        quiet=False,
        use_cookies=False,
        remaining_ok=True,
    )
    if downloaded is None:
        print("Drive folder download failed. Check link-sharing permissions and Drive download limits.", file=sys.stderr)
        return 1

    files = []
    for path in sorted(output.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in MODEL_SUFFIXES:
            continue
        relative = path.relative_to(output).as_posix()
        files.append({
            "file": relative,
            "kind": "model" if path.suffix.lower() == ".pth" else "index",
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "enabled": False,
        })

    catalog = {
        "schema_version": 1,
        "library": "Juliette TTS",
        "source_folder_url": args.folder_url,
        "models": files,
        "notes": [
            "Files are cataloged, not activated.",
            "Pair each .index with its matching .pth manually before inference.",
            "Verify model source, architecture, and usage rights before loading."
        ],
    }
    catalog_path = output / "catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Scanned {len(files)} RVC files. Catalog: {catalog_path}")
    print("No model was activated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
