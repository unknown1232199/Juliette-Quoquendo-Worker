"""Small Python adapter for the Juliette Quoquendo worker.

Set QUOQUENDO_WORKER to the compiled worker path and QUOQUENDO_DATA to the
LTTS7 data directory containing the voice .vcf files.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path


class QuoquendoError(RuntimeError):
    pass


def synthesize(text: str, voice: str = "Jorge") -> bytes:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must not be empty")
    if len(text) > 4000:
        raise ValueError("text exceeds the 4000-character limit")

    worker = os.environ.get("QUOQUENDO_WORKER", "").strip()
    data_dir = os.environ.get("QUOQUENDO_DATA", "").strip()
    if not worker or not Path(worker).is_file():
        raise QuoquendoError("QUOQUENDO_WORKER does not point to an existing worker binary")
    if not data_dir or not Path(data_dir).is_dir():
        raise QuoquendoError("QUOQUENDO_DATA does not point to an LTTS7 data directory")

    request = json.dumps(
        {"data_dir": data_dir, "voice": voice, "text": text},
        ensure_ascii=False,
    )
    try:
        completed = subprocess.run(
            [worker],
            input=request + "\\n",
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise QuoquendoError("Quoquendo worker timed out") from exc
    except OSError as exc:
        raise QuoquendoError(f"could not start Quoquendo worker: {exc}") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"worker exited with code {completed.returncode}"
        raise QuoquendoError(detail)

    try:
        response = json.loads(completed.stdout.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        detail = completed.stderr.strip() or "worker returned invalid JSON"
        raise QuoquendoError(detail) from exc

    if not response.get("ok"):
        raise QuoquendoError(response.get("error") or "speech generation failed")
    try:
        wav = base64.b64decode(response["wav_base64"], validate=True)
    except (KeyError, ValueError) as exc:
        raise QuoquendoError("worker returned invalid WAV data") from exc

    if not wav.startswith(b"RIFF") or wav[8:12] != b"WAVE":
        raise QuoquendoError("worker output is not a valid WAV container")
    return wav
