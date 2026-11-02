"""Feed fixed-size windows to Silero VAD and retrieve completed utterances."""

import numpy as np
from config import MIN_SEGMENT_SECONDS, SAMPLE_RATE


class VadProcessor:
    def __init__(self, detector, window_size: int):
        self.detector = detector
        self.window_size = window_size
        self.pending = np.empty(0, dtype=np.float32)

    def accept(self, samples: np.ndarray) -> list[np.ndarray]:
        self.pending = np.concatenate((self.pending, samples))
        while len(self.pending) >= self.window_size:
            self.detector.accept_waveform(self.pending[:self.window_size])
            self.pending = self.pending[self.window_size:]
        return self._completed()

    def flush(self) -> list[np.ndarray]:
        if len(self.pending):
            self.detector.accept_waveform(self.pending)
            self.pending = np.empty(0, dtype=np.float32)
        self.detector.flush()
        return self._completed()

    def reset(self) -> None:
        self.detector.reset()
        self.pending = np.empty(0, dtype=np.float32)

    def _completed(self) -> list[np.ndarray]:
        segments = []
        while not self.detector.empty():
            samples = np.asarray(self.detector.front.samples, dtype=np.float32).copy()
            self.detector.pop()
            if len(samples) >= MIN_SEGMENT_SECONDS * SAMPLE_RATE:
                segments.append(samples)
        return segments
