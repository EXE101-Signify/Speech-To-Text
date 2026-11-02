"""List input devices and probe their usable sample rates."""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.audio_capture import choose_sample_rate, list_microphones


def main() -> int:
    try:
        devices = list_microphones()
        if not devices:
            print("Không tìm thấy microphone. Kiểm tra kết nối và quyền truy cập Windows.")
            return 1
        for device in devices:
            try:
                rate = choose_sample_rate(device.index)
                print(f"[{device.index}] {device.name}: thu ở {rate} Hz")
            except Exception as exc:
                print(f"[{device.index}] {device.name}: không dùng được ({exc})")
        return 0
    except Exception as exc:
        print(f"Không thể kiểm tra microphone: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
