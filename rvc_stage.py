"""Async post-processing stage for generated TTS audio.

RVC inference runs in Juliette-RVC-Engine. This stage only forwards the WAV
created by the existing TTS provider and a model ID enabled in the local
catalog. The remote engine independently requires the model to be active.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from rvc_adapter import RVCError, convert_wav

MAX_AUDIO = 12 * 1024 * 1024
CATALOG_PATH = Path(__file__).with_name("rvc_models.json")


def load_catalog() -> dict:
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"models": []}
    return data if isinstance(data, dict) else {"models": []}


def available_models() -> list[dict]:
    models = load_catalog().get("models", [])
    if not isinstance(models, list):
        return []
    return [
        item for item in models
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and item.get("id")
    ]


def get_model(model_id: str) -> dict | None:
    return next((item for item in available_models()
                 if item["id"] == model_id and item.get("enabled") is True), None)


def model_exists(model_id: str) -> bool:
    return get_model(model_id) is not None


def service_configured() -> bool:
    return bool(
        os.getenv("JULIETTE_RVC_URL", "").strip().startswith("https://")
        and os.getenv("JULIETTE_RVC_API_KEY", "").strip()
    )


async def process_tts_audio(audio: bytes, config: dict) -> bytes:
    """Apply RVC only when enabled and an enabled model is selected."""
    if not isinstance(config, dict) or not config.get("rvc_enabled", False):
        return audio

    model_id = str(config.get("rvc_model", "")).strip()
    if not model_id:
        return audio
    if get_model(model_id) is None:
        raise RVCError(f"RVC model is missing or disabled: {model_id}")
    if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
        if config.get("rvc_fallback", True):
            return audio
        raise RVCError("RVC only accepts WAV audio from the TTS provider")
    if len(audio) > MAX_AUDIO:
        if config.get("rvc_fallback", True):
            return audio
        raise RVCError("TTS WAV exceeds the 12 MB RVC limit")

    try:
        converted = await asyncio.to_thread(convert_wav, audio, model_id)
        if len(converted) > MAX_AUDIO:
            raise RVCError("Converted WAV exceeds the 12 MB limit")
        return converted
    except Exception:
        if config.get("rvc_fallback", True):
            return audio
        raise
