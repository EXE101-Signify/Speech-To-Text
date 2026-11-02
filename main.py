"""Vietnamese speech recognition desktop entry point."""

import sys
from PySide6.QtWidgets import QApplication
from app.ui import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Vietnamese Speech-to-Text")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
