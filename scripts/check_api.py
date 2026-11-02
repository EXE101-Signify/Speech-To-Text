"""Smoke test REST and WebSocket with the installed model and example WAV."""
import wave
import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from config import ZIPFORMER_DIR

sample = ZIPFORMER_DIR / "test_wavs" / "0.wav"
with TestClient(app) as client:
    assert client.get("/api/v1/health").json()["model_loaded"]
    with sample.open("rb") as f:
        response = client.post("/api/v1/transcriptions", files={"file": ("sample.wav", f, "audio/wav")})
    response.raise_for_status()
    print("REST:", response.json()["data"])
    with wave.open(str(sample), "rb") as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2
        rate = wav.getframerate()
        with client.websocket_connect("/api/v1/stt/stream") as ws:
            ws.send_json({"type":"start", "sample_rate":rate, "channels":1, "encoding":"pcm_s16le", "language":"vi"})
            print("WebSocket:", ws.receive_json())
            while chunk := wav.readframes(1600):
                ws.send_bytes(chunk)
            ws.send_json({"type":"stop"})
            while True:
                message = ws.receive_json()
                print("WebSocket:", message)
                if message["type"] in ("session.completed", "error"):
                    assert message["type"] == "session.completed"
                    break
