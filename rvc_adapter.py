"""Optional HTTP adapter for converting generated TTS audio with RVC.

RVC inference is intentionally kept outside Wispbyte. Configure
JULIETTE_RVC_URL to a trusted conversion service implementing the JSON
contract documented in docs/rvc-integration.md.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request


class RVCError(RuntimeError):
    pass


def convert_wav(wav: bytes, model: str, *, endpoint: str | None = None,
                timeout: float = 90.0) -> bytes:
    """Convert a WAV byte string using a configured remote RVC service."""
    if not isinstance(wav, bytes) or len(wav) < 12:
        raise ValueError("wav must contain audio bytes")
    if not wav.startswith(b"RIFF") or wav[8:12] != b"WAVE":
        raise ValueError("input must be a WAV file")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must not be empty")

    url = (endpoint or os.environ.get("JULIETTE_RVC_URL", "")).strip()
    if not url:
        raise RVCError("JULIETTE_RVC_URL is not configured")
    if not url.startswith("https://"):
        raise RVCError("RVC endpoint must use HTTPS")

    payload = json.dumps({
        "model": model,
        "input_format": "wav",
        "audio_base64": base64.b64encode(wav).decode("ascii"),
    }).encode("utf-8")
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
