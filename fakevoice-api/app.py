import os
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response

app = FastAPI(title="Juliette FakeVoice API", version="1.1.0")
MODEL_ID = os.getenv("FAKEVOICE_MODEL_ID", "kasane-teto-gpt-sovits").strip()
API_KEY = os.getenv("FAKEVOICE_API_KEY", "").strip()
UPSTREAM = os.getenv("TETO_TTS_URL", "").strip().rstrip("/")
DEFAULT_LANGUAGE = os.getenv("TETO_TTS_LANGUAGE", "auto").strip().lower()
TIMEOUT = float(os.getenv("TETO_TTS_TIMEOUT", "240"))
MAX_TEXT = int(os.getenv("FAKEVOICE_MAX_TEXT", "1200"))
ALLOWED_LANGUAGES = {"ja", "en", "zh", "ja_en", "zh_en", "auto"}


def check_auth(authorization: str | None) -> None:
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "Juliette FakeVoice API", "status": "ok"}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "upstream_configured": bool(UPSTREAM)}


@app.get("/v1/models")
async def models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    check_auth(authorization)
    return {
        "object": "list",
        "data": [{
            "id": MODEL_ID,
            "object": "model",
            "owned_by": "juliette-fakevoice",
        }] if UPSTREAM else [],
    }


@app.post("/v1/audio/speech")
async def speech(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    check_auth(authorization)
    if not UPSTREAM:
        raise HTTPException(status_code=503, detail="TETO_TTS_URL is not configured")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    text = str(body.get("input", "")).strip()
    if not text or len(text) > MAX_TEXT:
        raise HTTPException(status_code=400, detail=f"input must contain 1 to {MAX_TEXT} characters")

    model = str(body.get("model", MODEL_ID))
    if model != MODEL_ID:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model}")

    if str(body.get("response_format") or "wav").lower() != "wav":
        raise HTTPException(status_code=400, detail="This Teto backend currently supports WAV only")

    language = str(body.get("language") or DEFAULT_LANGUAGE).lower()
    if language not in ALLOWED_LANGUAGES:
        language = DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in ALLOWED_LANGUAGES else "auto"

    payload: dict[str, str] = {"text": text, "language": language}
    for key in ("ref_audio", "ref_text"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = value.strip()

    timeout = httpx.Timeout(TIMEOUT, connect=20.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            upstream_response = await client.post(f"{UPSTREAM}/tts", json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Teto TTS request timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot reach Teto TTS: {type(exc).__name__}") from exc

    if upstream_response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Teto TTS returned HTTP {upstream_response.status_code}: {upstream_response.text[:500]}",
        )

    audio = upstream_response.content
    if not audio:
        raise HTTPException(status_code=502, detail="Teto TTS returned empty audio")
    content_type = upstream_response.headers.get("content-type", "")
    if "json" in content_type or "text/" in content_type:
        raise HTTPException(status_code=502, detail="Teto TTS did not return audio bytes")
    if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
        raise HTTPException(status_code=502, detail="Teto TTS response is not a valid WAV file")

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="speech.wav"'},
    )
