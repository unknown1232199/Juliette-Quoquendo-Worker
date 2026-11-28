#!/usr/bin/env python3
"""Safely sync RVC support into Juliette without replacing the bot or bridge.

Run from the Wispbyte server root:
    python install_rvc.py

Updates only RVC support files and patches the existing Loquendo Cog to add
/rvc_drive. bot.py, .env, WhatsApp bridge files, and startup settings are untouched.
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
FILES = ("rvc_adapter.py", "rvc_stage.py", "rvc_models.json", "rvc_drive_support.py")
LOQUENDO_FILE = "loquendo.py"
ROOT = Path(__file__).resolve().parent
TIMEOUT = 45

RVC_COMMAND = '''    @app_commands.command(name="rvc_drive", description="Registra el enlace de Google Drive de Kasane Teto")
    @app_commands.describe(url="Enlace compartido de Google Drive del archivo ZIP")
    async def rvc_drive(self, interaction: discord.Interaction, url: str):
        if not self.owner_only(interaction):
            await interaction.response.send_message("Solo el administrador puede registrar el modelo RVC.", ephemeral=True)
            return
        try:
            direct_url = register_drive_model(url)
            self.config["rvc_enabled"] = False
            save_config(self.config)
            await interaction.response.send_message(
                "Enlace de Kasane Teto registrado en rvc_models.json.\\n"
                f"Descarga: {direct_url}\\n"
                "RVC sigue desactivado hasta verificar el modelo y configurar el servicio remoto. "
                "En Drive, el archivo debe permitir acceso a cualquier persona con el enlace.",
                ephemeral=True
            )
        except Exception as exc:
            await interaction.response.send_message(f"No pude registrar el Drive: {exc}", ephemeral=True)

'''


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


def preserve_registered_drive(downloads: dict[str, bytes]) -> None:
    local_path = ROOT / "rvc_models.json"
    if not local_path.exists():
        return
    try:
        local_catalog = json.loads(local_path.read_text(encoding="utf-8"))
        remote_catalog = json.loads(downloads["rvc_models.json"].decode("utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return

    def teto(catalog):
        models = catalog.get("models", []) if isinstance(catalog, dict) else []
        return next((item for item in models
                     if isinstance(item, dict)
                     and item.get("id") == "kasane-teto-synthv-rvc-v2"), None)

    local_model = teto(local_catalog)
    remote_model = teto(remote_catalog)
    if not local_model or not remote_model:
        return
    local_url = local_model.get("download_url", "")
    if local_url.startswith("https://drive.google.com/"):
        remote_model["download_url"] = local_url
        remote_model["download_page"] = local_model.get("download_page", local_url)
        remote_model["enabled"] = False
        remote_model["archive_format"] = "zip"
        downloads["rvc_models.json"] = (
            json.dumps(remote_catalog, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")


def patch_loquendo(source: str) -> str:
    import_line = "from rvc_stage import process_tts_audio, available_models, service_configured"
    support_import = "from rvc_drive_support import register_drive_model"
    if support_import not in source:
        if import_line not in source:
            raise RuntimeError("loquendo.py does not contain the expected RVC import.")
        source = source.replace(import_line, import_line + "\n" + support_import, 1)

    if "async def rvc_drive(" not in source:
        marker = '    @app_commands.command(name="rvc",'
        if marker not in source:
            raise RuntimeError("loquendo.py does not contain the existing /rvc command.")
        source = source.replace(marker, RVC_COMMAND + marker, 1)

    ast.parse(source, filename=LOQUENDO_FILE)
    if "async def rvc_drive(" not in source or support_import not in source:
        raise RuntimeError("Could not install the /rvc_drive command.")
    return source


def validate(downloads: dict[str, bytes]) -> None:
    for name in ("rvc_adapter.py", "rvc_stage.py", "rvc_drive_support.py"):
        ast.parse(downloads[name].decode("utf-8"), filename=name)
    catalog = json.loads(downloads["rvc_models.json"].decode("utf-8"))
    if not isinstance(catalog, dict) or not isinstance(catalog.get("models"), list):
        raise RuntimeError("Invalid RVC model catalog")
    teto = next((m for m in catalog["models"]
                 if isinstance(m, dict)
                 and m.get("id") == "kasane-teto-synthv-rvc-v2"), None)
    if not teto or teto.get("enabled") is not False:
        raise RuntimeError("Kasane Teto must remain disabled until inference is tested")
    if not teto.get("download_url", "").startswith("https://drive.google.com/"):
        raise RuntimeError("Kasane Teto model URL is not a trusted Google Drive HTTPS URL")


def main() -> int:
    print("Downloading RVC support files from GitHub...")
    downloads = {name: fetch(name) for name in FILES}
    preserve_registered_drive(downloads)
    validate(downloads)

    loquendo_path = ROOT / LOQUENDO_FILE
    if not loquendo_path.is_file():
        raise RuntimeError("loquendo.py is missing; refusing to install a disconnected command.")
    original_loquendo = loquendo_path.read_text(encoding="utf-8")
    patched_loquendo = patch_loquendo(original_loquendo)
    staged_data = dict(downloads)
    staged_data[LOQUENDO_FILE] = patched_loquendo.encode("utf-8")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    staged: dict[str, Path] = {}
    try:
        for name, data in staged_data.items():
            fd, temp_name = tempfile.mkstemp(prefix=".rvc-sync-", dir=ROOT)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            staged[name] = Path(temp_name)

        targets = (*FILES, LOQUENDO_FILE)
        for name in targets:
            target = ROOT / name
            if target.exists():
                backup = ROOT / f"{name}.backup-{stamp}"
                if backup.exists():
                    raise RuntimeError(f"Backup already exists: {backup.name}")
                shutil.copy2(target, backup)
                print(f"Backup: {backup.name}")
        for name in targets:
            os.replace(staged[name], ROOT / name)
            print(f"Updated: {name}")

    finally:
        for path in staged.values():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    print("RVC support and /rvc_drive installed. No bot restart was performed.")
    print("The model remains disabled until remote download validation and inference tests pass.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"RVC sync failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
