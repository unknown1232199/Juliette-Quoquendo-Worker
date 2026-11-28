from __future__ import annotations

import base64
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
import wave
from pathlib import Path
from typing import Any

import gdown
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

APP_DIR = Path(__file__).resolve().parent
CACHE_DIR = Path(os.getenv("RVC_MODEL_CACHE", str(APP_DIR / "models"))).resolve()
WORK_DIR = Path(os.getenv("RVC_WORK_DIR", str(APP_DIR / "work"))).resolve()
API_KEY = os.getenv("JULIETTE_RVC_API_KEY", "").strip()
RVC_BIN = os.getenv("RVC_BIN", "rvc")
MAX_AUDIO = 12 * 1024 * 1024
MAX_MODEL_DOWNLOAD = int(os.getenv("RVC_MAX_DOWNLOAD_BYTES", str(3 * 1024**3)))
DOWNLOAD_LOCK = threading.Lock()
INFER_LOCK = threading.Lock()

app = FastAPI(title="Juliette RVC Inference API", version="0.1.0")


class ConvertRequest(BaseModel):
    model: str = Field(min_length=1, max_length=128)
    input_format: str = "wav"
    audio_base64: str
    model_download_url: str | None = None
    model_download_format: str = "drive-folder"


def authorize(value: str | None) -> None:
    if not API_KEY or value != f"Bearer {API_KEY}":
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


def validate_drive_folder(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {"drive.google.com", "www.drive.google.com"}:
        raise HTTPException(status_code=400, detail="Only shared Google Drive HTTPS links are accepted")
    if "/folders/" not in parsed.path:
        raise HTTPException(status_code=400, detail="Expected a shared Google Drive folder URL")
    return url


def locate_model(model_id: str) -> tuple[Path, Path | None]:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", model_id):
        raise HTTPException(status_code=400, detail="Invalid model id")
    roots = [p for p in CACHE_DIR.rglob("*.pth") if p.is_file()]
    if not roots:
        raise HTTPException(status_code=404, detail="No .pth checkpoints found in the downloaded Drive library")
    if len(roots) == 1:
        checkpoint = roots[0]
    else:
        normalized = re.sub(r"[^a-z0-9]", "", model_id.lower())
        matches = [p for p in roots if normalized in re.sub(r"[^a-z0-9]", "", p.stem.lower())
                   or "teto" in p.stem.lower() and "teto" in model_id.lower()]
        if len(matches) != 1:
            raise HTTPException(status_code=409, detail=f"Model selection is ambiguous: {len(matches)} checkpoints found")
        checkpoint = matches[0]
    indexes = list(checkpoint.parent.glob("*.index"))
    index = indexes[0] if len(indexes) == 1 else None
    if len(indexes) > 1:
        named = [p for p in indexes if p.stem.casefold() in {checkpoint.stem.casefold(), checkpoint.stem.casefold() + "_added"}]
        if len(named) == 1:
            index = named[0]
        else:
            raise HTTPException(status_code=409, detail="Multiple .index files found; cannot pair them safely")
    if checkpoint.stat().st_size <= 1024 * 1024:
        raise HTTPException(status_code=422, detail="Checkpoint is unexpectedly small; refusing to load it")
    if index and index.stat().st_size == 0:
        raise HTTPException(status_code=422, detail="Index file is empty")
    return checkpoint, index


def download_library(url: str) -> None:
    validate_drive_folder(url)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with DOWNLOAD_LOCK:
        # Reuse a populated cache. Refreshing is an explicit operator action.
        if any(CACHE_DIR.rglob("*.pth")):
            return
        staging = CACHE_DIR.with_name(CACHE_DIR.name + ".staging")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        result = gdown.download_folder(
            url=url, output=str(staging), quiet=True,
            use_cookies=False, remaining_ok=True,
        )
        if not result:
            shutil.rmtree(staging, ignore_errors=True)
            raise HTTPException(status_code=502, detail="Google Drive folder download failed; check link sharing and quota")
        total = sum(p.stat().st_size for p in staging.rglob("*") if p.is_file())
        if total > MAX_MODEL_DOWNLOAD:
            shutil.rmtree(staging, ignore_errors=True)
            raise HTTPException(status_code=413, detail="Downloaded library exceeds configured size limit")
        if not any(staging.rglob("*.pth")):
            shutil.rmtree(staging, ignore_errors=True)
            raise HTTPException(status_code=422, detail="Drive folder contains no .pth checkpoint")
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
        staging.replace(CACHE_DIR)


def check_wav(data: bytes) -> None:
    if len(data) < 44 or len(data) > MAX_AUDIO or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise HTTPException(status_code=400, detail="Input must be a valid WAV under 12 MB")
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as f:
            f.write(data)
            f.flush()
            with wave.open(f.name, "rb") as wav:
                if wav.getnchannels() not in (1, 2) or wav.getframerate() < 8000:
                    raise HTTPException(status_code=400, detail="Unsupported WAV audio parameters")
    except (wave.Error, EOFError) as exc:
        raise HTTPException(status_code=400, detail="Malformed WAV file") from exc


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "Juliette RVC", "status": "ok"}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "model_cache_populated": any(CACHE_DIR.rglob("*.pth")) if CACHE_DIR.exists() else False,
            "rvc_cli": shutil.which(RVC_BIN) is not None}


@app.post("/convert")
def convert(body: ConvertRequest, authorization: str | None = Header(default=None)) -> dict[str, str]:
    authorize(authorization)
    if body.input_format.lower() != "wav":
        raise HTTPException(status_code=400, detail="Only WAV input is supported")
    if body.model_download_url:
        if body.model_download_format != "drive-folder":
            raise HTTPException(status_code=400, detail="Only drive-folder model sources are supported")
        download_library(body.model_download_url)
    checkpoint, index = locate_model(body.model)
    try:
        audio = base64.b64decode(body.audio_base64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="audio_base64 is invalid") from exc
    check_wav(audio)
    if not shutil.which(RVC_BIN):
        raise HTTPException(status_code=503, detail="RVC CLI is not installed on this host")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="juliette-rvc-", dir=WORK_DIR) as tmp:
        tmpdir = Path(tmp)
        input_path, output_path = tmpdir / "input.wav", tmpdir / "output.wav"
        input_path.write_bytes(audio)
        command = [RVC_BIN, "infer", "-m", str(checkpoint), "-i", str(input_path), "-o", str(output_path),
                   "--pitch", "0", "--f0-method", "rmvpe", "--index-rate", "0.75"]
        if index:
            command.extend(["--index", str(index)])
        try:
            with INFER_LOCK:
                result = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail="RVC inference timed out") from exc
        if result.returncode != 0 or not output_path.exists():
            detail = (result.stderr or result.stdout or "RVC inference failed")[-1200:]
            raise HTTPException(status_code=502, detail=detail)
        converted = output_path.read_bytes()
        check_wav(converted)
    return {"audio_base64": base64.b64encode(converted).decode("ascii"),
            "model": body.model, "model_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
