"""Local REST and WebSocket API for utterance-based Vietnamese STT."""
import asyncio
import hmac
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import soxr
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal

from app.model_manager import create_vad
from app.services.audio_processing import decode_wav, MAX_FILE_BYTES
from app.services.speech_recognition import SpeechRecognitionService
from app.vad_processor import VadProcessor

ORIGINS = [x.strip() for x in os.getenv("STT_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if x.strip()]
API_KEY = os.getenv("STT_API_KEY", "")
MAX_SESSIONS = int(os.getenv("STT_MAX_SESSIONS", "8"))
MAX_SECONDS = int(os.getenv("STT_MAX_SESSION_SECONDS", "600"))
MAX_FRAME = 32768
STATIC = Path(__file__).resolve().parents[1] / "static"
service = SpeechRecognitionService()
active_sessions = 0


@asynccontextmanager
async def lifespan(app):
    if os.getenv("STT_ENV", "development") == "production" and not API_KEY:
        raise RuntimeError("STT_API_KEY is required in production")
    await asyncio.to_thread(service.load_model)
    yield
    await asyncio.to_thread(service.shutdown)


app = FastAPI(title="Vietnamese Speech-to-Text", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-API-Key"])
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "error": {"message": exc.detail}})


def authenticated(value):
    return not API_KEY or hmac.compare_digest(value or "", API_KEY)


class StartMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["start"]
    sample_rate: int = Field(ge=8000, le=48000)
    channels: Literal[1]
    encoding: Literal["pcm_s16le"]
    language: Literal["vi"]
    api_key: str | None = None


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/v1/health")
async def health():
    return {"status": "ok" if service.recognizer else "error", "service": "vietnamese-speech-to-text",
            "model": "zipformer-vietnamese-30m-int8", "model_loaded": service.recognizer is not None}


@app.get("/api/v1/models/current")
async def model_info():
    return service.get_model_info()


@app.post("/api/v1/transcriptions")
async def transcription(request: Request, file: UploadFile = File(...), language: str = Form("vi")):
    if not authenticated(request.headers.get("x-api-key")):
        raise HTTPException(401, "API key không hợp lệ.")
    if language != "vi" or not (file.filename or "").lower().endswith(".wav"):
        raise HTTPException(400, "Chỉ hỗ trợ tiếng Việt và file WAV.")
    data = await file.read(MAX_FILE_BYTES + 1)
    await file.close()
    try:
        samples, duration = await asyncio.to_thread(decode_wav, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    try:
        text, elapsed = await asyncio.to_thread(service.transcribe_audio, samples)
    except Exception as exc:
        raise HTTPException(503, "Nhận dạng thất bại.") from exc
    return {"success": True, "data": {"text": text, "language": "vi",
            "duration_seconds": duration, "processing_time_ms": round(elapsed * 1000)}}


@app.websocket("/api/v1/stt/stream")
async def stream(ws: WebSocket):
    global active_sessions
    origin = ws.headers.get("origin")
    if (origin and origin not in ORIGINS) or active_sessions >= MAX_SESSIONS:
        await ws.close(code=1008)
        return
    active_sessions += 1
    await ws.accept()
    session_id = str(uuid.uuid4())
    sequence = 0
    started = time.monotonic()
    try:
        first = await asyncio.wait_for(ws.receive_text(), timeout=10)
        start = StartMessage.model_validate_json(first)
        if not authenticated(start.api_key or ws.headers.get("x-api-key")):
            raise ValueError("API key không hợp lệ.")
        detector, window = await asyncio.to_thread(
            create_vad, float(os.getenv("STT_VAD_THRESHOLD", "0.5")),
            float(os.getenv("STT_VAD_SILENCE", "0.5")), 20.0)
        vad = VadProcessor(detector, window)
        resampler = None if start.sample_rate == 16000 else soxr.ResampleStream(start.sample_rate, 16000, 1, dtype="float32")
        await ws.send_json({"type": "ready", "session_id": session_id, "sample_rate": 16000})

        async def emit(segments):
            nonlocal sequence
            for segment in segments:
                text, elapsed = await asyncio.to_thread(service.transcribe_audio, segment)
                if text:
                    sequence += 1
                    await ws.send_json({"type": "transcript.final", "session_id": session_id,
                                        "sequence": sequence, "text": text, "is_final": True,
                                        "processing_time_ms": round(elapsed * 1000)})

        while True:
            remaining = MAX_SECONDS - (time.monotonic() - started)
            if remaining <= 0:
                raise ValueError("Phiên đã vượt thời gian cho phép.")
            message = await asyncio.wait_for(ws.receive(), timeout=min(remaining, 30))
            if message["type"] == "websocket.disconnect":
                break
            if message.get("bytes") is not None:
                data = message["bytes"]
                if not data or len(data) > MAX_FRAME or len(data) % 2:
                    raise ValueError("Audio frame không hợp lệ hoặc quá lớn.")
                samples = np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768
                if resampler:
                    samples = resampler.resample_chunk(samples)
                await emit(await asyncio.to_thread(vad.accept, samples))
            elif message.get("text") is not None:
                command = json.loads(message["text"])
                if command.get("type") == "ping":
                    await ws.send_json({"type": "pong"})
                elif command.get("type") == "stop":
                    if resampler:
                        tail = resampler.resample_chunk(np.empty(0, np.float32), last=True)
                        await emit(await asyncio.to_thread(vad.accept, tail))
                    await emit(await asyncio.to_thread(vad.flush))
                    await ws.send_json({"type": "session.completed", "session_id": session_id})
                    break
                else:
                    raise ValueError("Lệnh không hợp lệ.")
    except WebSocketDisconnect:
        pass
    except (ValueError, ValidationError, json.JSONDecodeError, asyncio.TimeoutError) as exc:
        try:
            await ws.send_json({"type": "error", "message": str(exc) or "Phiên hết thời gian chờ."})
        except (RuntimeError, WebSocketDisconnect):
            pass
    except Exception:
        try:
            await ws.send_json({"type": "error", "message": "Xử lý âm thanh thất bại."})
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        active_sessions -= 1
        try:
            await ws.close()
        except RuntimeError:
            pass
