"""Decode bounded PCM WAV uploads and convert them to mono 16 kHz."""
import io
import wave
import numpy as np
import soxr

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_DURATION = 120


def decode_wav(data: bytes):
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("File WAV rỗng hoặc vượt quá 20 MB.")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            channels, width, rate, count = wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()
            if wav.getcomptype() != "NONE" or width != 2 or channels not in (1, 2) or not 8000 <= rate <= 48000:
                raise ValueError("Chỉ hỗ trợ WAV PCM 16-bit mono/stereo, 8–48 kHz.")
            if not count or count / rate > MAX_DURATION:
                raise ValueError("Thời lượng WAV phải từ 0 đến 120 giây.")
            raw = wav.readframes(count)
            if len(raw) != count * channels * width:
                raise ValueError("WAV bị cắt hoặc thiếu dữ liệu.")
            samples = np.frombuffer(raw, dtype="<i2").astype(np.float32).reshape(-1, channels).mean(axis=1) / 32768
            if rate != 16000:
                samples = soxr.resample(samples, rate, 16000).astype(np.float32)
            return samples, count / rate
    except (wave.Error, EOFError) as exc:
        raise ValueError("WAV không hợp lệ.") from exc
