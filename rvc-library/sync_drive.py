#!/usr/bin/env python3
"""Sync a shared Drive folder and build a review-only RVC model catalog.

Run this on the machine that will host RVC inference, never inside the bot.
Requires gdown unless --scan-only is used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_FOLDER_URL = "https://drive.google.com/drive/folders/1zUEGXqS5aK8wVSuHiUsGJiVOqQHGQI7i"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_folder_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.netloc in {"drive.google.com", "www.drive.google.com"} and "/folders/" in parsed.path


def model_key(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    stem = re.sub(r"(?i)(?:_|-)\d+epochs?$", "", path.stem)
    return (relative.parent / stem).as_posix().casefold()


def scan_library(root: Path, source_url: str) -> dict:
    root = root.resolve()
    model_files = sorted(p for p in root.rglob("*.pth") if p.is_file())
    index_files = sorted(p for p in root.rglob("*.index") if p.is_file())

    indexes_by_key: dict[str, list[Path]] = {}
    for path in index_files:
        indexes_by_key.setdefault(model_key(path, root), []).append(path)

    models = []
    used_indexes: set[Path] = set()
    warnings = []
    for model in model_files:
        key = model_key(model, root)
        matches = indexes_by_key.get(key, [])
        index = matches[0] if len(matches) == 1 else None
        if len(matches) > 1:
            warnings.append(f"Multiple index files appear to match {model.relative_to(root)}; pairing left unresolved.")
        if model.stat().st_size == 0:
            warnings.append(f"Empty model file: {model.relative_to(root)}")
        if index:
            used_indexes.add(index)
        models.append({
            "id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
            "name": model.stem,
            "model_file": model.relative_to(root).as_posix(),
            "model_size_bytes": model.stat().st_size,
            "model_sha256": sha256_file(model),
            "index_file": index.relative_to(root).as_posix() if index else None,
            "index_sha256": sha256_file(index) if index else None,
            "enabled": False,
            "status": "needs_review",
            "warnings": (["Model file is empty."] if model.stat().st_size == 0 else [])
                        + (["No unambiguous matching .index file found; index is optional for some models."] if not index else []),
        })

    for index in index_files:
        if index not in used_indexes:
            warnings.append(f"Unmatched index file: {index.relative_to(root)}")
    if not models:
        warnings.append("No .pth model files found.")

    return {
        "schema_version": 2,
        "library": "Juliette TTS",
        "source_folder_url": source_url,
        "models": models,
        "unmatched_index_files": [p.relative_to(root).as_posix() for p in index_files if p not in used_indexes],
        "warnings": warnings,
        "safety": {
            "all_models_disabled": True,
            "activation_requires_manual_review": True,
            "inference_backend_configured": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and catalog Juliette TTS RVC models.")
    parser.add_argument("--folder-url", default=DEFAULT_FOLDER_URL)
    parser.add_argument("--output", default="./voice-library")
    parser.add_argument("--scan-only", action="store_true", help="Catalog files already present; do not contact Google Drive.")
    args = parser.parse_args()

    if not safe_folder_url(args.folder_url):
        print("Refusing URL: use an HTTPS Google Drive folder URL.", file=sys.stderr)
        return 2

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    if not args.scan_only:
        try:
            import gdown
        except ImportError:
            print("Missing dependency. Install with: python -m pip install gdown", file=sys.stderr)
            return 2
        downloaded = gdown.download_folder(
            url=args.folder_url,
            output=str(output),
            quiet=False,
            use_cookies=False,
            remaining_ok=True,
        )
        if not downloaded:
            print("Drive download failed. Check link sharing and Google Drive quotas.", file=sys.stderr)
            return 1

    catalog = scan_library(output, args.folder_url)
    catalog_path = output / "catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Catalog created: {catalog_path}")
    print(f"Models found: {len(catalog['models'])}; unmatched indexes: {len(catalog['unmatched_index_files'])}")
    print("All models remain disabled. No inference or activation was performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
