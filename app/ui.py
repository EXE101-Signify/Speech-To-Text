"""PySide6 desktop interface."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QTextEdit,
    QVBoxLayout, QWidget,
)

from app.audio_capture import list_microphones
from app.workers import Pipeline


STYLE = """
QMainWindow, QWidget { background: #111827; color: #e5e7eb; font-family: 'Segoe UI'; }
QLabel#title { font-size: 25px; font-weight: 700; color: #f9fafb; }
QLabel#subtitle { color: #9ca3af; font-size: 12px; }
QFrame#card { background: #1f2937; border: 1px solid #374151; border-radius: 12px; }
QComboBox, QTextEdit { background: #111827; color: #f9fafb; border: 1px solid #4b5563;
    border-radius: 8px; padding: 8px; selection-background-color: #2563eb; }
QComboBox QAbstractItemView { background: #1f2937; color: white; }
QPushButton { background: #374151; color: #f9fafb; border: 1px solid #4b5563;
    border-radius: 8px; padding: 9px 15px; font-weight: 600; }
QPushButton:hover { background: #4b5563; }
QPushButton:disabled { color: #6b7280; background: #1f2937; }
QPushButton#start { background: #2563eb; border-color: #2563eb; }
QPushButton#start:hover { background: #1d4ed8; }
QProgressBar { background: #111827; border: 0; border-radius: 5px; height: 10px; }
QProgressBar::chunk { background: #38bdf8; border-radius: 5px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vietnamese Speech-to-Text")
        self.resize(900, 660)
        self.setMinimumSize(640, 480)
        self.setStyleSheet(STYLE)
        self._closing = False
        self._build()
        self.pipeline = Pipeline()
        self.pipeline.model_state.connect(self._model_state)
        self.pipeline.activity.connect(self.activity_label.setText)
        self.pipeline.level.connect(self.level_bar.setValue)
        self.pipeline.transcript.connect(self._append_transcript)
        self.pipeline.error.connect(self._error)
        self.pipeline.session_done.connect(self._session_done)
        self.pipeline.start_workers()
        self._refresh_microphones()

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(17)

        title = QLabel("Vietnamese Speech-to-Text")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("Nhận dạng tiếng Việt theo từng phát ngôn · Xử lý trên máy của bạn")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("card")
        controls = QVBoxLayout(card)
        controls.setContentsMargins(18, 16, 18, 16)
        controls.setSpacing(12)

        top = QHBoxLayout()
        top.addWidget(QLabel("MODEL"))
        self.model_label = QLabel("Loading")
        top.addWidget(self.model_label)
        top.addStretch()
        top.addWidget(QLabel("TRẠNG THÁI"))
        self.activity_label = QLabel("Idle")
        top.addWidget(self.activity_label)
        controls.addLayout(top)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Microphone"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        device_row.addWidget(self.device_combo, 1)
        refresh = QPushButton("Làm mới")
        refresh.clicked.connect(self._refresh_microphones)
        device_row.addWidget(refresh)
        controls.addLayout(device_row)

        button_row = QHBoxLayout()
        self.start_button = QPushButton("Bắt đầu")
        self.start_button.setObjectName("start")
        self.start_button.clicked.connect(self._start)
        self.pause_button = QPushButton("Tạm dừng")
        self.pause_button.clicked.connect(self._pause)
        self.stop_button = QPushButton("Dừng")
        self.stop_button.clicked.connect(self._stop)
        for button in (self.start_button, self.pause_button, self.stop_button):
            button_row.addWidget(button)
        button_row.addStretch()
        controls.addLayout(button_row)
        controls.addWidget(QLabel("Mức âm lượng"))
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setTextVisible(False)
        controls.addWidget(self.level_bar)
        layout.addWidget(card)

        transcript_header = QHBoxLayout()
        transcript_header.addWidget(QLabel("VĂN BẢN NHẬN DẠNG"))
        transcript_header.addStretch()
        self.timing_label = QLabel("Câu gần nhất: —")
        transcript_header.addWidget(self.timing_label)
        layout.addLayout(transcript_header)
        self.text = QTextEdit()
        self.text.setPlaceholderText("Văn bản sẽ xuất hiện sau khi bạn kết thúc một câu nói…")
        self.text.setFont(QFont("Segoe UI", 12))
        layout.addWidget(self.text, 1)

        actions = QHBoxLayout()
        for label, handler in (
            ("Copy Text", self._copy), ("Clear Text", self.text.clear),
            ("Export TXT", self._export),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.statusBar().showMessage("Đang tải model…")
        self._update_buttons()

    def _refresh_microphones(self):
        current = self.device_combo.currentData()
        self.device_combo.clear()
        try:
            devices = list_microphones()
            for device in devices:
                self.device_combo.addItem(
                    f"{device.name}  ·  {device.default_samplerate} Hz", device.index
                )
            if current is not None:
                match = self.device_combo.findData(current)
                if match >= 0:
                    self.device_combo.setCurrentIndex(match)
            if not devices:
                self.statusBar().showMessage("Không tìm thấy microphone. Kiểm tra kết nối và quyền truy cập.")
        except Exception as exc:
            self._error(f"Không thể liệt kê microphone: {exc}")
        self._update_buttons()

    def _update_buttons(self):
        active = getattr(self, "pipeline", None) and self.pipeline.session is not None
        ready = getattr(self, "pipeline", None) and self.pipeline.ready
        self.start_button.setEnabled(bool(ready and not active and self.device_combo.count()))
        self.pause_button.setEnabled(bool(active))
        self.stop_button.setEnabled(bool(active))
        self.device_combo.setEnabled(not active)

    def _model_state(self, state: str, detail: str):
        self.model_label.setText(state)
        self.model_label.setStyleSheet(
            "color: #34d399;" if state == "Ready" else
            "color: #f87171;" if state == "Error" else "color: #fbbf24;"
        )
        self.statusBar().showMessage(detail)
        self._update_buttons()

    def _start(self):
        try:
            self.pipeline.start(int(self.device_combo.currentData()))
            self.pause_button.setText("Tạm dừng")
            self._update_buttons()
        except Exception as exc:
            self._error(str(exc))

    def _pause(self):
        paused = self.pipeline.toggle_pause()
        self.pause_button.setText("Tiếp tục" if paused else "Tạm dừng")

    def _stop(self):
        self.pipeline.stop()
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)

    def _session_done(self):
        self._update_buttons()

    def _append_transcript(self, text: str, elapsed: float, duration: float):
        self.text.append(text)
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())
        self.timing_label.setText(f"Câu gần nhất: {elapsed:.2f} s · âm thanh {duration:.1f} s · {len(text)} ký tự")
        self.statusBar().showMessage("Đã nhận dạng một phát ngôn.")

    def _error(self, message: str):
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "Lỗi", message)
        self._update_buttons()

    def _copy(self):
        QApplication.clipboard().setText(self.text.toPlainText())
        self.statusBar().showMessage("Đã sao chép văn bản.")

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Xuất văn bản", str(Path.home() / "transcript.txt"), "Text (*.txt)")
        if path:
            try:
                Path(path).write_text(self.text.toPlainText(), encoding="utf-8")
                self.statusBar().showMessage(f"Đã xuất: {path}")
            except OSError as exc:
                self._error(f"Không thể xuất file TXT: {exc}")

    def closeEvent(self, event):
        if self.pipeline.threads_finished():
            event.accept()
            return
        event.ignore()
        if not self._closing:
            self._closing = True
            self.setEnabled(False)
            self.statusBar().showMessage("Đang đóng các worker…")
            self.pipeline.close()
            self._close_timer = QTimer(self)
            self._close_timer.timeout.connect(self._finish_close)
            self._close_timer.start(100)

    def _finish_close(self):
        if self.pipeline.threads_finished():
            self._close_timer.stop()
            self.close()
