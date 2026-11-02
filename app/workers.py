"""Bounded audio pipeline. Capture, VAD and ASR run outside the GUI thread."""

import queue
import threading
from dataclasses import dataclass, field

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, Signal

from app.audio_capture import choose_sample_rate
from app.audio_resampling import StreamingResampler
from app.model_manager import create_recognizer, create_vad
from app.speech_recognizer import recognize
from app.vad_processor import VadProcessor
from config import AUDIO_QUEUE_BLOCKS, CPU_THREADS, SPEECH_QUEUE_SEGMENTS


@dataclass
class CaptureSession:
    device_index: int
    audio: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=AUDIO_QUEUE_BLOCKS))
    stop: threading.Event = field(default_factory=threading.Event)
    pause: threading.Event = field(default_factory=threading.Event)
    capture_done: threading.Event = field(default_factory=threading.Event)
    reset_vad: threading.Event = field(default_factory=threading.Event)
    capture_thread: threading.Thread | None = None


class Pipeline(QObject):
    model_state = Signal(str, str)
    activity = Signal(str)
    level = Signal(int)
    transcript = Signal(str, float, float)
    error = Signal(str)
    session_done = Signal()

    def __init__(self):
        super().__init__()
        self.shutdown = threading.Event()
        self.session: CaptureSession | None = None
        self.sessions: queue.Queue[CaptureSession] = queue.Queue(maxsize=1)
        self.speech: queue.Queue[np.ndarray] = queue.Queue(maxsize=SPEECH_QUEUE_SEGMENTS)
        self._ready = set()
        self._failed = False
        self._asr_thread = threading.Thread(target=self._asr_loop, name="ASR", daemon=True)
        self._vad_thread = threading.Thread(target=self._vad_loop, name="VAD", daemon=True)
    def start_workers(self) -> None:
        self._asr_thread.start()
        self._vad_thread.start()

    @property
    def ready(self) -> bool:
        return self._ready == {"asr", "vad"} and not self._failed

    def _mark_ready(self, part: str) -> None:
        self._ready.add(part)
        if self.ready:
            self.model_state.emit("Ready", "Model sẵn sàng")

    def _fail(self, message: str) -> None:
        self._failed = True
        self.model_state.emit("Error", message)
        self.error.emit(message)
        if self.session:
            self.session.stop.set()

    def start(self, device_index: int) -> None:
        if not self.ready:
            raise RuntimeError("Model chưa sẵn sàng.")
        if self.session is not None:
            raise RuntimeError("Microphone đang được sử dụng.")
        session = CaptureSession(device_index)
        self.session = session
        self.sessions.put_nowait(session)
        session.capture_thread = threading.Thread(
            target=self._capture_loop, args=(session,), name="Capture", daemon=True
        )
        session.capture_thread.start()
        self.activity.emit("Đang mở microphone…")

    def toggle_pause(self) -> bool:
        session = self.session
        if session is None or session.stop.is_set():
            return False
        if session.pause.is_set():
            session.pause.clear()
            self.activity.emit("Listening")
            return False
        session.pause.set()
        session.reset_vad.set()
        while True:
            try:
                session.audio.get_nowait()
            except queue.Empty:
                break
        self.activity.emit("Paused")
        self.level.emit(0)
        return True

    def stop(self) -> None:
        if self.session:
            self.session.stop.set()
            self.activity.emit("Đang dừng…")
            self.level.emit(0)

    def close(self) -> None:
        self.shutdown.set()
        self.stop()

    def threads_finished(self) -> bool:
        threads = [self._asr_thread, self._vad_thread]
        if self.session and self.session.capture_thread:
            threads.append(self.session.capture_thread)
        return all(not thread.is_alive() for thread in threads)

    def _capture_loop(self, session: CaptureSession) -> None:
        try:
            rate = choose_sample_rate(session.device_index)
            resampler = StreamingResampler(rate)
            frames = max(1, round(rate * 0.1))
            with sd.InputStream(
                device=session.device_index, channels=1, dtype="float32",
                samplerate=rate, blocksize=frames,
            ) as stream:
                self.activity.emit("Listening")
                was_paused = False
                while not session.stop.is_set() and not self.shutdown.is_set():
                    raw, overflowed = stream.read(frames)
                    if overflowed:
                        raise RuntimeError("Microphone bị tràn bộ đệm; máy tính không xử lý âm thanh kịp.")
                    if session.pause.is_set():
                        was_paused = True
                        continue
                    if was_paused:
                        resampler = StreamingResampler(rate)
                        was_paused = False
                    samples = resampler.process(raw[:, 0])
                    peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
                    self.level.emit(min(100, int(peak * 140)))
                    try:
                        session.audio.put(samples, timeout=0.05)
                    except queue.Full:
                        raise RuntimeError("Hàng đợi âm thanh đã đầy; hãy giảm tải CPU hoặc tăng STT_CPU_THREADS.")
        except (sd.PortAudioError, OSError) as exc:
            self.error.emit(f"Không thể thu âm từ microphone. Kiểm tra quyền truy cập, thiết bị và ứng dụng khác: {exc}")
        except Exception as exc:
            self.error.emit(f"Thu âm bị gián đoạn: {exc}")
        finally:
            if "resampler" in locals() and not session.pause.is_set():
                tail = resampler.finish()
                if len(tail) and not self.shutdown.is_set():
                    try:
                        session.audio.put(tail, timeout=0.2)
                    except queue.Full:
                        self.error.emit("Hàng đợi âm thanh đầy khi kết thúc thu âm.")
            session.stop.set()
            session.capture_done.set()
            self.level.emit(0)

    def _vad_loop(self) -> None:
        try:
            detector, window_size = create_vad()
            processor = VadProcessor(detector, window_size)
            self._mark_ready("vad")
        except Exception as exc:
            self._fail(str(exc))
            return
        while not self.shutdown.is_set():
            try:
                session = self.sessions.get(timeout=0.1)
            except queue.Empty:
                continue
            processor.reset()
            was_paused = False
            try:
                while True:
                    if session.reset_vad.is_set():
                        processor.reset()
                        session.reset_vad.clear()
                    if session.pause.is_set():
                        if not was_paused:
                            processor.reset()
                            was_paused = True
                    elif was_paused:
                        processor.reset()
                        was_paused = False
                    try:
                        samples = session.audio.get(timeout=0.05)
                    except queue.Empty:
                        if session.capture_done.is_set():
                            break
                        continue
                    if not session.pause.is_set():
                        for segment in processor.accept(samples):
                            self._enqueue_speech(segment)
                    if session.capture_done.is_set() and session.audio.empty():
                        break
                if not session.pause.is_set():
                    for segment in processor.flush():
                        self._enqueue_speech(segment)
                processor.reset()
            except Exception as exc:
                self.error.emit(f"Phát hiện giọng nói thất bại: {exc}")
                session.stop.set()
            finally:
                self.session = None
                self.session_done.emit()
                self.activity.emit("Idle")

    def _enqueue_speech(self, segment: np.ndarray) -> None:
        try:
            self.speech.put(segment, timeout=0.2)
            self.activity.emit("Processing")
        except queue.Full:
            raise RuntimeError("Hàng đợi nhận dạng đã đầy; âm thanh mới bị dừng để tránh mất dữ liệu âm thầm.")

    def _asr_loop(self) -> None:
        try:
            recognizer = create_recognizer(CPU_THREADS)
            self._mark_ready("asr")
        except Exception as exc:
            self._fail(str(exc))
            return
        while not self.shutdown.is_set() or self._vad_thread.is_alive() or not self.speech.empty():
            try:
                segment = self.speech.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                text, elapsed = recognize(recognizer, segment)
                if text:
                    self.transcript.emit(text, elapsed, len(segment) / 16000)
                if self.session and not self.session.pause.is_set() and not self.session.stop.is_set():
                    self.activity.emit("Listening")
            except Exception as exc:
                self.error.emit(f"Nhận dạng câu thất bại: {exc}")
