"""Optional HTTP adapter for converting generated TTS audio with RVC.

The RVC model stays on the remote inference service. Juliette sends a
catalog-controlled Google Drive download URL so the service can fetch and
cache the selected model on first use. No inference runs on Wispbyte.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request


class RVCError(RuntimeError):
    pass


def convert_wav(wav: bytes, model: str, *, model_url: str | None = None,
                endpoint: str | None = None, timeout: float = 180.0) -> bytes:
    """Convert WAV bytes using a remote service and a catalog model URL."""
    if not isinstance(wav, bytes) or len(wav) < 12:
        raise ValueError("wav must contain audio bytes")
    if not wav.startswith(b"RIFF") or wav[8:12] != b"WAVE":
        raise ValueError("input must be a WAV file")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must not be empty")
    if model_url:
        if not model_url.startswith("https://drive.google.com/"):
            raise RVCError("model download URL must be a trusted Google Drive HTTPS URL")

    url = (endpoint or os.environ.get("JULIETTE_RVC_URL", "")).strip()
    if not url:
        raise RVCError("JULIETTE_RVC_URL is not configured")
    if not url.startswith("https://"):
        raise RVCError("RVC endpoint must use HTTPS")

    payload_data = {
        "model": model,
        "input_format": "wav",
        "audio_base64": base64.b64encode(wav).decode("ascii"),
    }
    if model_url:
        payload_data["model_download_url"] = model_url
        payload_data["model_archive_format"] = "zip"
    payload = json.dumps(payload_data).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise RVCError(f"RVC service returned HTTP {response.status}")
            if response.headers.get_content_type() != "application/json":
                raise RVCError("RVC service returned a non-JSON response")
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RVCError(f"RVC service returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RVCError(f"could not reach RVC service: {exc.reason}") from exc
    except (TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RVCError(f"invalid or timed-out RVC response: {exc}") from exc

    try:
        converted = base64.b64decode(result["audio_base64"], validate=True)
    except (KeyError, ValueError, TypeError) as exc:
        raise RVCError("RVC service response has no valid audio_base64") from exc
    if len(converted) < 12 or not converted.startswith(b"RIFF") or converted[8:12] != b"WAVE":
        raise RVCError("RVC service did not return a valid WAV")
    return converted
