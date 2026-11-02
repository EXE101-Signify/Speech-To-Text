"""Model validation and Sherpa-ONNX construction."""

from config import MODEL_FILES, SAMPLE_RATE, VAD_PATH, ZIPFORMER_DIR


def validate_models() -> None:
    missing = [str(ZIPFORMER_DIR / name) for name in MODEL_FILES
               if not (ZIPFORMER_DIR / name).is_file()]
    if not VAD_PATH.is_file():
        missing.append(str(VAD_PATH))
    if missing:
        raise FileNotFoundError(
            "Thiếu model: " + ", ".join(missing)
            + ". Hãy chạy: python scripts/download_models.py"
        )
    empty = [str(ZIPFORMER_DIR / name) for name in MODEL_FILES
             if (ZIPFORMER_DIR / name).stat().st_size == 0]
    if VAD_PATH.stat().st_size == 0:
        empty.append(str(VAD_PATH))
    if empty:
        raise ValueError("File model rỗng: " + ", ".join(empty))


def create_recognizer(num_threads: int):
    validate_models()
    if num_threads < 1:
        raise ValueError("Số CPU threads phải lớn hơn 0.")
    import sherpa_onnx
    try:
        return sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(ZIPFORMER_DIR / "encoder.int8.onnx"),
            decoder=str(ZIPFORMER_DIR / "decoder.onnx"),
            joiner=str(ZIPFORMER_DIR / "joiner.int8.onnx"),
            tokens=str(ZIPFORMER_DIR / "tokens.txt"),
            num_threads=num_threads,
            sample_rate=SAMPLE_RATE,
            feature_dim=80,
            decoding_method="greedy_search",
            provider="cpu",
        )
    except Exception as exc:
        raise RuntimeError(f"Không khởi tạo được Zipformer ONNX: {exc}") from exc


def create_vad(threshold=0.5, min_silence=0.5, max_speech=20.0):
    validate_models()
    import sherpa_onnx
    try:
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(VAD_PATH)
        config.silero_vad.threshold = threshold
        config.silero_vad.min_silence_duration = min_silence
        config.silero_vad.min_speech_duration = 0.25
        config.silero_vad.max_speech_duration = max_speech
        config.sample_rate = SAMPLE_RATE
        return sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30), config.silero_vad.window_size
    except Exception as exc:
        raise RuntimeError(f"Không khởi tạo được Silero VAD: {exc}") from exc
