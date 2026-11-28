"""HTTP adapter for the separate Juliette-RVC-Engine service.

The bot sends WAV bytes produced by its TTS provider. The remote engine owns
the model catalog and performs conversion; no RVC inference runs in this repo.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
import uuid


class RVCError(RuntimeError):
    pass


def _field(boundary: str, name: str, value: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n"
    ).encode("utf-8")


def _multipart(model: str, wav: bytes, semitone_shift: int,
               retrieval_blend: float) -> tuple[bytes, str]:
    boundary = "----JulietteRVC" + uuid.uuid4().hex
    chunks = [
        _field(boundary, "model_id", model),
        _field(boundary, "semitone_shift", str(semitone_shift)),
        _field(boundary, "retrieval_blend", str(retrieval_blend)),
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="tts-input.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode("ascii"),
        wav,
        b"\r\n",
        f"--{boundary}--\r\n".encode("ascii"),
    ]
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def convert_wav(wav: bytes, model: str, *, endpoint: str | None = None,
                timeout: float = 180.0, semitone_shift: int = 0,
                retrieval_blend: float = 0.0) -> bytes:
    """Convert TTS-generated WAV through POST /v1/rvc/convert."""
    if not isinstance(wav, bytes) or len(wav) < 44:
        raise ValueError("wav must contain a complete WAV file")
    if not wav.startswith(b"RIFF") or wav[8:12] != b"WAVE":
        raise ValueError("input must be a WAV file")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model must not be empty")
    if not -24 <= int(semitone_shift) <= 24:
        raise ValueError("semitone_shift must be between -24 and 24")
    if not 0.0 <= float(retrieval_blend) <= 1.0:
        raise ValueError("retrieval_blend must be between 0 and 1")

    base_url = (endpoint or os.environ.get("JULIETTE_RVC_URL", "")).strip().rstrip("/")
    api_key = os.environ.get("JULIETTE_RVC_API_KEY", "").strip()
    if not base_url:
        raise RVCError("JULIETTE_RVC_URL is not configured")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RVCError("RVC endpoint must use HTTPS")
    if not api_key:
        raise RVCError("JULIETTE_RVC_API_KEY is not configured")

    payload, content_type = _multipart(model, wav, int(semitone_shift), float(retrieval_blend))
    request = urllib.request.Request(
        base_url + "/v1/rvc/convert",
        data=payload,
        headers={
            "Content-Type": content_type,
            "Accept": "audio/wav",
            "X-API-Key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            converted = response.read()
            response_type = response.headers.get("Content-Type", "").lower()
            if response.status != 200:
                raise RVCError(f"RVC service returned HTTP {response.status}")
            if not response_type.startswith("audio/wav"):
                raise RVCError("RVC service returned a non-WAV response")
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace").strip()
        raise RVCError(f"RVC service returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RVCError(f"could not reach RVC service: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RVCError("RVC request timed out") from exc

    if len(converted) < 44 or not converted.startswith(b"RIFF") or converted[8:12] != b"WAVE":
        raise RVCError("RVC service did not return a valid WAV")
    return converted
