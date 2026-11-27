"""Async post-processing stage for generated TTS audio.

This module is intended to be imported by Juliette's Discord Cog. It never
captures microphone audio and never performs RVC inference locally.
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
    catalog = load_catalog()
    models = catalog.get("models", [])
    if not isinstance(models, list):
        return []
    return [
        item for item in models
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and item.get("id")
    ]


def model_exists(model_id: str) -> bool:
    return any(item["id"] == model_id for item in available_models())


def service_configured() -> bool:
    return os.getenv("JULIETTE_RVC_URL", "").strip().startswith("https://")


async def process_tts_audio(audio: bytes, config: dict) -> bytes:
    """Apply RVC only when enabled and a model is explicitly selected.

    With RVC disabled or no model selected, the original bytes are returned.
    On conversion errors, fallback is controlled by config['rvc_fallback'].
    """
    if not isinstance(config, dict):
        return audio
    if not config.get("rvc_enabled", False):
        return audio

    model_id = str(config.get("rvc_model", "")).strip()
    if not model_id:
        return audio
    if not model_exists(model_id):
        raise RVCError(f"RVC model is not registered: {model_id}")
    if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
        raise RVCError("RVC only accepts WAV audio from the TTS provider")
    if len(audio) > MAX_AUDIO:
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
