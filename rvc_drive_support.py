"""Register a Google Drive-hosted RVC archive in Juliette's model catalog."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CATALOG_PATH = Path(__file__).with_name("rvc_models.json")
MODEL_ID = "kasane-teto-synthv-rvc-v2"


def register_drive_model(shared_url: str) -> str:
    if not isinstance(shared_url, str):
        raise ValueError("Pega un enlace compartido de Google Drive.")
    shared_url = shared_url.strip()
    parsed = urlparse(shared_url)
    if parsed.scheme != "https" or parsed.hostname != "drive.google.com":
        raise ValueError("El enlace debe ser HTTPS y pertenecer a drive.google.com.")
    if parsed.username or parsed.password:
        raise ValueError("El enlace no puede incluir credenciales.")

    match = re.search(r"/file/d/([A-Za-z0-9_-]+)", parsed.path)
    file_id = match.group(1) if match else parse_qs(parsed.query).get("id", [""])[0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", file_id):
        raise ValueError("No pude extraer un ID de archivo válido del enlace de Drive.")

    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("No pude leer rvc_models.json.") from exc

    models = catalog.get("models") if isinstance(catalog, dict) else None
    if not isinstance(models, list):
        raise RuntimeError("El catálogo RVC no tiene una lista de modelos válida.")
    model = next((item for item in models
                  if isinstance(item, dict) and item.get("id") == MODEL_ID), None)
    if model is None:
        raise RuntimeError("No encontré Kasane Teto en el catálogo RVC.")

    model["download_page"] = shared_url
    model["download_url"] = direct_url
    model["archive_format"] = "zip"
    model["enabled"] = False
    model["notes"] = (
        "Drive URL registered. Keep disabled until the remote RVC service "
        "downloads, validates, caches, and successfully tests this archive."
    )

    temp_path = CATALOG_PATH.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(CATALOG_PATH)
    return direct_url
