"""Decode one completed speech segment without altering its text."""

from time import perf_counter
import numpy as np
from config import SAMPLE_RATE


def recognize(recognizer, samples: np.ndarray) -> tuple[str, float]:
    started = perf_counter()
    stream = recognizer.create_stream()
    stream.accept_waveform(SAMPLE_RATE, np.ascontiguousarray(samples, dtype=np.float32))
    recognizer.decode_stream(stream)
    return stream.result.text.strip(), perf_counter() - started
