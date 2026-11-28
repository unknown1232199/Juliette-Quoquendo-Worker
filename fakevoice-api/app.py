import os
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response

app = FastAPI(title="Juliette FakeVoice API", version="1.0.0")

MODEL_ID = os.getenv("FAKEVOICE_MODEL_ID", "kasane-teto-gpt-sovits")
API_KEY = os.getenv("FAKEVOICE_API_KEY", "").strip()
UPSTREAM = os.getenv("GPT_SOVITS_URL", "").strip().rstrip("/")
REF_AUDIO = os.getenv("GPT_SOVITS_REF_AUDIO_PATH", "").strip()
PROMPT_TEXT = os.getenv("GPT_SOVITS_PROMPT_TEXT", "").strip()
PROMPT_LANG = os.getenv("GPT_SOVITS_PROMPT_LANG", "ja").strip()
DEFAULT_TEXT_LANG = os.getenv("GPT_SOVITS_TEXT_LANG", "auto").strip()
TIMEOUT = float(os.getenv("GPT_SOVITS_TIMEOUT", "180"))
MAX_TEXT = int(os.getenv("FAKEVOICE_MAX_TEXT", "1200"))


def check_auth(authorization: str | None) -> None:
    if not API_KEY:
        return
    expected = f"Bearer {API_KEY}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "Juliette FakeVoice API", "status": "ok"}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "upstream_configured": bool(UPSTREAM),
        "reference_audio_configured": bool(REF_AUDIO),
        "prompt_text_configured": bool(PROMPT_TEXT),
    }


@app.get("/v1/models")
async def models(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    check_auth(authorization)
    ready = bool(UPSTREAM and REF_AUDIO and PROMPT_TEXT)
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_ID,
                "object": "model",
                "owned_by": "juliette-fakevoice",
            }
        ] if ready else [],
    }


@app.post("/v1/audio/speech")
async def speech(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Response:
    check_auth(authorization)

    if not UPSTREAM:
        raise HTTPException(status_code=503, detail="GPT_SOVITS_URL is not configured")
    if not REF_AUDIO or not PROMPT_TEXT:
        raise HTTPException(
            status_code=503,
            detail="Configure GPT_SOVITS_REF_AUDIO_PATH and GPT_SOVITS_PROMPT_TEXT",
        )

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    text = str(body.get("input", "")).strip()
    if not text or len(text) > MAX_TEXT:
        raise HTTPException(
            status_code=400,
            detail=f"input must contain 1 to {MAX_TEXT} characters",
        )

    model = str(body.get("model", MODEL_ID))
    if model != MODEL_ID:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model}")

    text_lang = str(body.get("language") or DEFAULT_TEXT_LANG)
    media_type = str(body.get("response_format") or "wav").lower()
    if media_type not in {"wav", "raw", "ogg", "aac"}:
        media_type = "wav"

    payload = {
        "text": text,
        "text_lang": text_lang,
        "ref_audio_path": REF_AUDIO,
        "prompt_text": PROMPT_TEXT,
        "prompt_lang": PROMPT_LANG,
        "media_type": media_type,
        "streaming_mode": False,
        "text_split_method": "cut5",
        "speed_factor": 1.0,
    }

    timeout = httpx.Timeout(TIMEOUT, connect=15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            upstream_response = await client.post(f"{UPSTREAM}/tts", json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="GPT-SoVITS request timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot reach GPT-SoVITS: {type(exc).__name__}") from exc

    if upstream_response.status_code != 200:
        detail = upstream_response.text[:500]
        raise HTTPException(
            status_code=502,
            detail=f"GPT-SoVITS returned HTTP {upstream_response.status_code}: {detail}",
        )

    audio = upstream_response.content
    if not audio:
        raise HTTPException(status_code=502, detail="GPT-SoVITS returned empty audio")

    content_type = upstream_response.headers.get("content-type", "audio/wav")
    if "application/json" in content_type or "text/" in content_type:
        raise HTTPException(status_code=502, detail="GPT-SoVITS did not return audio bytes")

    output_type = {
        "wav": "audio/wav",
        "raw": "application/octet-stream",
        "ogg": "audio/ogg",
        "aac": "audio/aac",
    }.get(media_type, "audio/wav")

    return Response(
        content=audio,
        media_type=output_type,
        headers={"Content-Disposition": 'inline; filename="speech.wav"'},
    )
