"""Application settings and verified model asset names."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODELS_DIR = Path(os.environ.get("MODEL_PATH", str(ROOT / "models"))).resolve()
ZIPFORMER_DIR = MODELS_DIR / "zipformer-vi-30m-int8"
VAD_PATH = MODELS_DIR / "silero_vad.onnx"
MODEL_FILES = ("encoder.int8.onnx", "decoder.onnx", "joiner.int8.onnx", "tokens.txt")
SAMPLE_RATE = 16_000
CPU_THREADS = max(1, int(os.environ.get("SHERPA_NUM_THREADS", os.environ.get("STT_CPU_THREADS", "2"))))
AUDIO_QUEUE_BLOCKS = 128
SPEECH_QUEUE_SEGMENTS = 32
MIN_SEGMENT_SECONDS = 0.25

MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09.tar.bz2"
)
VAD_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "silero_vad.onnx"
)
