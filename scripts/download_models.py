"""Download and validate the verified Vietnamese Zipformer and Silero models."""

import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import MODEL_FILES, MODEL_URL, MODELS_DIR, VAD_PATH, VAD_URL, ZIPFORMER_DIR

ARCHIVE_NAME = "sherpa-onnx-zipformer-vi-30M-int8-2026-02-09"
MIN_ARCHIVE_BYTES = 20_000_000
MIN_VAD_BYTES = 100_000
MIN_FILE_BYTES = {
    "encoder.int8.onnx": 15_000_000,
    "decoder.onnx": 1_000_000,
    "joiner.int8.onnx": 100_000,
    "tokens.txt": 1_000,
}


def _download(url: str, destination: Path, minimum: int) -> None:
    temp = destination.with_name(destination.name + ".part")
    try:
        with urllib.request.urlopen(url, timeout=60) as response, temp.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                total += len(chunk)
                print(f"\rĐã tải {total / 1_000_000:.1f} MB", end="", flush=True)
        print()
        if temp.stat().st_size < minimum:
            raise ValueError(f"File tải xuống quá nhỏ ({temp.stat().st_size} bytes).")
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)


def _valid_model(directory: Path) -> bool:
    return all(
        (directory / name).is_file()
        and (directory / name).stat().st_size >= MIN_FILE_BYTES[name]
        for name in MODEL_FILES
    )


def _extract_model(archive: Path) -> None:
    with tempfile.TemporaryDirectory(dir=MODELS_DIR) as temp_dir:
        temp_dir = Path(temp_dir)
        with tarfile.open(archive, "r:bz2") as tar:
            for member in tar.getmembers():
                path = Path(member.name)
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise ValueError(f"Archive chứa loại tệp không an toàn: {member.name}")
                if path.is_absolute() or ".." in path.parts or path.parts[0] != ARCHIVE_NAME:
                    raise ValueError(f"Archive chứa đường dẫn không an toàn: {member.name}")
                if member.isfile():
                    if path.name in MIN_FILE_BYTES and member.size < MIN_FILE_BYTES[path.name]:
                        raise ValueError(f"File model trong archive quá nhỏ: {member.name}")
                    target = temp_dir.joinpath(*path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = tar.extractfile(member)
                    if source is None:
                        raise ValueError(f"Không đọc được: {member.name}")
                    with source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
        extracted = temp_dir / ARCHIVE_NAME
        if not _valid_model(extracted):
            raise ValueError("Archive thiếu encoder, decoder, joiner hoặc tokens hợp lệ.")
        if ZIPFORMER_DIR.exists():
            shutil.rmtree(ZIPFORMER_DIR)
        extracted.replace(ZIPFORMER_DIR)


def main() -> int:
    MODELS_DIR.mkdir(exist_ok=True)
    try:
        if _valid_model(ZIPFORMER_DIR):
            print("Zipformer đã có; bỏ qua tải lại.")
        else:
            archive = MODELS_DIR / f"{ARCHIVE_NAME}.tar.bz2"
            if not archive.is_file() or archive.stat().st_size < MIN_ARCHIVE_BYTES:
                print("Đang tải Zipformer…")
                _download(MODEL_URL, archive, MIN_ARCHIVE_BYTES)
            print("Đang kiểm tra và giải nén Zipformer…")
            try:
                _extract_model(archive)
            except (tarfile.TarError, ValueError, OSError):
                archive.unlink(missing_ok=True)
                raise
            archive.unlink(missing_ok=True)
        if VAD_PATH.is_file() and VAD_PATH.stat().st_size >= MIN_VAD_BYTES:
            print("Silero VAD đã có; bỏ qua tải lại.")
        else:
            print("Đang tải Silero VAD…")
            _download(VAD_URL, VAD_PATH, MIN_VAD_BYTES)
        print("Model đã sẵn sàng:", ZIPFORMER_DIR, VAD_PATH)
        return 0
    except Exception as exc:
        print(f"Tải model thất bại: {exc}", file=sys.stderr)
        print("Kiểm tra Internet và chạy lại lệnh để thử lại.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
