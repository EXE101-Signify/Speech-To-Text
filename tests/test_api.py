import io
import unittest
import wave
from unittest.mock import patch

import numpy as np
from fastapi.testclient import TestClient
from app.main import app, service
from app.services.audio_processing import decode_wav


def wav_bytes(rate=8000):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(np.zeros(rate * 2, dtype="<i2").tobytes())
    return output.getvalue()


class FakeVad:
    def accept_waveform(self, data): pass
    def empty(self): return True
    def flush(self): pass


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.load = patch.object(service, "load_model", lambda: setattr(service, "recognizer", object()))
        self.decode = patch.object(service, "transcribe_audio", return_value=("xin chào", .01))
        self.vad = patch("app.main.create_vad", return_value=(FakeVad(), 512))
        self.load.start(); self.decode.start(); self.vad.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.vad.stop(); self.decode.stop(); self.load.stop()

    def test_health_and_model(self):
        self.assertTrue(self.client.get("/api/v1/health").json()["model_loaded"])
        self.assertEqual(self.client.get("/api/v1/models/current").json()["sample_rate"], 16000)

    def test_upload_and_invalid(self):
        result = self.client.post("/api/v1/transcriptions", files={"file": ("a.wav", wav_bytes(), "audio/wav")})
        self.assertEqual(result.json()["data"]["text"], "xin chào")
        self.assertEqual(self.client.post("/api/v1/transcriptions", files={"file": ("x.wav", b"bad", "audio/wav")}).status_code, 400)
        with self.assertRaises(ValueError): decode_wav(b"bad")
        self.assertEqual(len(decode_wav(wav_bytes())[0]), 16000)

    def test_websocket_start_stop_and_disconnect(self):
        with self.client.websocket_connect("/api/v1/stt/stream") as ws:
            ws.send_json({"type":"start","sample_rate":16000,"channels":1,"encoding":"pcm_s16le","language":"vi"})
            self.assertEqual(ws.receive_json()["type"], "ready")
            ws.send_bytes(bytes(3200))
            ws.send_json({"type":"stop"})
            self.assertEqual(ws.receive_json()["type"], "session.completed")
        with self.client.websocket_connect("/api/v1/stt/stream") as ws:
            ws.send_json({"type":"start","sample_rate":16000,"channels":1,"encoding":"pcm_s16le","language":"vi"})
            self.assertEqual(ws.receive_json()["type"], "ready")

    def test_multiple_sessions(self):
        start = {"type":"start","sample_rate":16000,"channels":1,"encoding":"pcm_s16le","language":"vi"}
        with self.client.websocket_connect("/api/v1/stt/stream") as first:
            first.send_json(start)
            a = first.receive_json()
            with self.client.websocket_connect("/api/v1/stt/stream") as second:
                second.send_json(start)
                b = second.receive_json()
                self.assertNotEqual(a["session_id"], b["session_id"])
                second.send_json({"type":"stop"})
                self.assertEqual(second.receive_json()["type"], "session.completed")
            first.send_json({"type":"stop"})
            self.assertEqual(first.receive_json()["type"], "session.completed")

    def test_model_error(self):
        self.decode.stop()
        with patch.object(service, "transcribe_audio", side_effect=RuntimeError("error")):
            r = self.client.post("/api/v1/transcriptions", files={"file": ("a.wav", wav_bytes(), "audio/wav")})
            self.assertEqual(r.status_code, 503)
        self.decode.start()


if __name__ == "__main__":
    unittest.main()
