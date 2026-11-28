#!/usr/bin/env python3
"""Safely sync the RVC support files from this repository into Juliette's root.

Run from the Wispbyte server root:
    python install_rvc.py

Only the three RVC support files are updated. bot.py, loquendo.py, .env,
WhatsApp bridge files, and startup settings are deliberately untouched.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://raw.githubusercontent.com/unknown1232199/Juliette-Quoquendo-Worker/main/"
FILES = ("rvc_adapter.py", "rvc_stage.py", "rvc_models.json")
ROOT = Path(__file__).resolve().parent
TIMEOUT = 45


def fetch(name: str) -> bytes:
    request = urllib.request.Request(
        BASE + name,
        headers={"User-Agent": "Juliette-RVC-Sync/1.0", "Accept": "text/plain"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        if response.status != 200:
            raise RuntimeError(f"GitHub returned HTTP {response.status} for {name}")
        data = response.read(2 * 1024 * 1024 + 1)
    if not data or len(data) > 2 * 1024 * 1024:
        raise RuntimeError(f"Unexpected file size for {name}")
    return data


def validate(downloads: dict[str, bytes]) -> None:
    for name in ("rvc_adapter.py", "rvc_stage.py"):
        ast.parse(downloads[name].decode("utf-8"), filename=name)
    catalog = json.loads(downloads["rvc_models.json"].decode("utf-8"))
    if not isinstance(catalog, dict) or not isinstance(catalog.get("models"), list):
        raise RuntimeError("Invalid RVC model catalog")
    teto = next((m for m in catalog["models"]
                 if isinstance(m, dict)
                 and m.get("id") == "kasane-teto-synthv-rvc-v2"), None)
    if not teto or teto.get("enabled") is not False:
        raise RuntimeError("Kasane Teto must remain disabled until inference is tested")
    url = teto.get("download_url", "")
    if not url.startswith("https://drive.google.com/"):
        raise RuntimeError("Kasane Teto model URL is not a trusted Google Drive HTTPS URL")


def main() -> int:
    print("Downloading the three RVC support files from the repository...")
    downloads = {name: fetch(name) for name in FILES}
    validate(downloads)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    staged: dict[str, Path] = {}
    try:
        for name, data in downloads.items():
            fd, temp_name = tempfile.mkstemp(prefix=".rvc-sync-", dir=ROOT)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            staged[name] = Path(temp_name)

        for name in FILES:
            target = ROOT / name
            if target.exists():
                backup = ROOT / f"{name}.backup-{stamp}"
                if backup.exists():
                    raise RuntimeError(f"Backup already exists: {backup.name}")
                shutil.copy2(target, backup)
                print(f"Backup: {backup.name}")
            os.replace(staged[name], target)
            print(f"Updated: {name}")

    finally:
        for path in staged.values():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    print("RVC support files synchronized. No bot restart was performed.")
    print("Kasane Teto remains disabled; a trusted HTTPS RVC inference service is still required.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"RVC sync failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
