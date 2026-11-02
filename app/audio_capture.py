"""Microphone enumeration and band-limited streaming resampling to 16 kHz."""

from dataclasses import dataclass
import numpy as np
from config import SAMPLE_RATE


def _sounddevice():
    # Import PortAudio only when an actual microphone operation is requested.
    import sounddevice
    return sounddevice


@dataclass(frozen=True)
class Microphone:
    index: int
    name: str
    default_samplerate: int


def list_microphones() -> list[Microphone]:
    sd = _sounddevice()
    devices = sd.query_devices()
    return [Microphone(i, str(item["name"]), int(round(item["default_samplerate"])))
            for i, item in enumerate(devices) if item["max_input_channels"] > 0]


def choose_sample_rate(device_index: int) -> int:
    sd = _sounddevice()
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

