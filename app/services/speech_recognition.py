"""Shared offline model. Serialize access to the Sherpa recognizer."""
import threading
from app.model_manager import create_recognizer
from app.speech_recognizer import recognize
from config import CPU_THREADS


class SpeechRecognitionService:
    def __init__(self):
        self.recognizer = None
        self.lock = threading.Lock()

    def load_model(self):
        self.recognizer = create_recognizer(CPU_THREADS)

    def transcribe_audio(self, samples):
        with self.lock:
            if self.recognizer is None:
                raise RuntimeError("Model chưa sẵn sàng")
            return recognize(self.recognizer, samples)

    def get_model_info(self):
        return {"name": "zipformer-vietnamese-30m-int8", "version": "2026-02-09",
                "inference_engine": "sherpa-onnx", "language": "vi",
                "sample_rate": 16000, "inference_mode": "offline-transducer-vad",
                "device": "cpu"}

    def shutdown(self):
        with self.lock:
            self.recognizer = None
