"""Microphone enumeration and band-limited streaming resampling to 16 kHz."""

from dataclasses import dataclass
import numpy as np
import sounddevice as sd
import soxr
from config import SAMPLE_RATE


@dataclass(frozen=True)
class Microphone:
    index: int
    name: str
    default_samplerate: int


def list_microphones() -> list[Microphone]:
    devices = sd.query_devices()
    return [Microphone(i, str(item["name"]), int(round(item["default_samplerate"])))
            for i, item in enumerate(devices) if item["max_input_channels"] > 0]


def choose_sample_rate(device_index: int) -> int:
    try:
        sd.check_input_settings(device=device_index, channels=1, dtype="float32", samplerate=SAMPLE_RATE)
        return SAMPLE_RATE
    except sd.PortAudioError:
        device = sd.query_devices(device_index, "input")
        rate = int(round(device["default_samplerate"]))
        if rate <= 0:
            raise RuntimeError("Microphone không có sample rate hợp lệ.")
        sd.check_input_settings(device=device_index, channels=1, dtype="float32", samplerate=rate)
        return rate


class StreamingResampler:
    """Use SoXR's stateful filter to avoid aliasing and chunk boundary drift."""

    def __init__(self, input_rate: int):
        self.input_rate = input_rate
        self.stream = (
            None if input_rate == SAMPLE_RATE
            else soxr.ResampleStream(input_rate, SAMPLE_RATE, 1, dtype="float32")
        )

    def process(self, samples: np.ndarray) -> np.ndarray:
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            return samples
        if self.stream is None:
            return samples.copy()
        return self.stream.resample_chunk(samples, last=False)

    def finish(self) -> np.ndarray:
        if self.stream is None:
            return np.empty(0, np.float32)
        return self.stream.resample_chunk(np.empty(0, np.float32), last=True)
