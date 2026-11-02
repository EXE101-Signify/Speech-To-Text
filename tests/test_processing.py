"""Small deterministic checks for the audio pipeline's boundary behavior."""

import sys
import types
import unittest

import numpy as np

try:
    import sounddevice
except ImportError:
    sys.modules["sounddevice"] = types.ModuleType("sounddevice")

from app.audio_capture import StreamingResampler
from app.vad_processor import VadProcessor


class ResamplerTests(unittest.TestCase):
    def test_48k_to_16k_has_no_chunk_drift(self):
        rate = 48_000
        source = np.sin(2 * np.pi * 440 * np.arange(rate) / rate).astype(np.float32)
        resampler = StreamingResampler(rate)
        chunks = [resampler.process(source[i:i + 777]) for i in range(0, len(source), 777)]
        result = np.concatenate(chunks + [resampler.finish()])
        self.assertEqual(len(result), 16_000)
        expected = source[::3]
        self.assertLess(float(np.mean(np.abs(result[200:-200] - expected[200:-200]))), 0.01)

    def test_44k1_to_16k_has_no_chunk_drift(self):
        source = np.ones(44_100, np.float32) * 0.25
        resampler = StreamingResampler(44_100)
        chunks = [resampler.process(source[i:i + 1001]) for i in range(0, len(source), 1001)]
        result = np.concatenate(chunks + [resampler.finish()])
        self.assertEqual(len(result), 16_000)
        np.testing.assert_allclose(result[200:-200], 0.25, atol=0.01)


class _FakeDetector:
    def __init__(self):
        self.segments = []
        self.front = None

    def accept_waveform(self, samples):
        self.segments.append(np.array(samples))

    def empty(self):
        return True

    def flush(self):
        pass

    def reset(self):
        self.segments.clear()


class VadWindowTests(unittest.TestCase):
    def test_every_sample_reaches_detector(self):
        detector = _FakeDetector()
        processor = VadProcessor(detector, 512)
        signal = np.arange(1500, dtype=np.float32)
        for chunk in np.array_split(signal, 7):
            processor.accept(chunk)
        processor.flush()
        np.testing.assert_array_equal(np.concatenate(detector.segments), signal)


if __name__ == "__main__":
    unittest.main()
