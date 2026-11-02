"""Independent checks before launching the GUI.

Usage: python scripts/diagnose.py [--wav path.wav] [--vad-wav] [--mic seconds]
"""

import argparse
import sys
import time
import wave
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", type=Path)
    parser.add_argument("--vad-wav", action="store_true", help="Đưa WAV mẫu qua Silero VAD trước ASR")
    parser.add_argument("--mic", type=float, default=0, metavar="SECONDS")
    parser.add_argument("--mic-device", type=int, help="Chỉ số microphone trong danh sách")
    args = parser.parse_args()
    try:
        import numpy as np
        import sounddevice as sd
        import sherpa_onnx
        from app.audio_capture import choose_sample_rate, list_microphones, StreamingResampler
        from app.model_manager import create_recognizer, create_vad, validate_models
        from app.speech_recognizer import recognize
        from app.vad_processor import VadProcessor
        from config import CPU_THREADS, SAMPLE_RATE

        print("Sherpa-ONNX:", getattr(sherpa_onnx, "__version__", "đã import"))
        devices = list_microphones()
        print("Microphone:", len(devices))
        for device in devices:
            print(f"  [{device.index}] {device.name}")
        validate_models()
        print("File model: OK")
        started = time.perf_counter()
        recognizer = create_recognizer(CPU_THREADS)
        print(f"Zipformer: OK, tải {time.perf_counter() - started:.2f} s")
        detector, window = create_vad()
        processor = VadProcessor(detector, window)
        print("Silero VAD: OK")
        if args.wav:
            with wave.open(str(args.wav), "rb") as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != SAMPLE_RATE:
                    raise ValueError("WAV cần mono, PCM 16-bit, 16 kHz.")
                samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768
            text, elapsed = recognize(recognizer, samples)
            print(f"WAV: {text}\nThời gian: {elapsed:.2f} s; độ dài: {len(text)} ký tự")
            if args.vad_wav:
                segments = []
                for i in range(0, len(samples), 1600):
                    segments.extend(processor.accept(samples[i:i + 1600]))
                segments.extend(processor.flush())
                print(f"VAD trên WAV: {len(segments)} phát ngôn")
                if not segments:
                    raise RuntimeError("Silero VAD không tìm thấy phát ngôn trong WAV mẫu.")
                for number, segment in enumerate(segments, 1):
                    result, duration = recognize(recognizer, segment)
                    print(f"  {number}: {result} ({duration:.2f} s, {len(result)} ký tự)")
                processor.reset()
        if args.mic:
            if not devices:
                raise RuntimeError("Không có microphone để kiểm thử.")
            device = next((d for d in devices if d.index == args.mic_device), None) if args.mic_device is not None else devices[0]
            if device is None:
                raise ValueError(f"Không tìm thấy microphone #{args.mic_device}.")
            rate = choose_sample_rate(device.index)
            resampler = StreamingResampler(rate)
            print(f"Nói vào {device.name} trong {args.mic:g} giây…")
            end = time.monotonic() + args.mic
            with sd.InputStream(device=device.index, channels=1, dtype="float32", samplerate=rate) as stream:
                while time.monotonic() < end:
                    audio, overflow = stream.read(round(rate * .1))
                    if overflow:
                        raise RuntimeError("Microphone bị tràn bộ đệm.")
                    for segment in processor.accept(resampler.process(audio[:, 0])):
                        text, elapsed = recognize(recognizer, segment)
                        print(f"VAD+ASR: {text} ({elapsed:.2f} s, {len(text)} ký tự)")
            for segment in processor.accept(resampler.finish()):
                text, elapsed = recognize(recognizer, segment)
                print(f"VAD+ASR: {text} ({elapsed:.2f} s, {len(text)} ký tự)")
            for segment in processor.flush():
                text, elapsed = recognize(recognizer, segment)
                print(f"VAD+ASR: {text} ({elapsed:.2f} s, {len(text)} ký tự)")
        print("Kiểm tra hoàn tất.")
        return 0
    except Exception as exc:
        print(f"Kiểm tra thất bại: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
