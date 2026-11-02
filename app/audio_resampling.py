"""Audio sample-rate conversion shared by desktop and backend code."""

import numpy as np
import soxr

from config import SAMPLE_RATE


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
