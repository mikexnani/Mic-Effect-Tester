import sys
import traceback
from collections import deque
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

import utils
from audio_engine import AudioEngine
from ui.dialogs import AINRDialog, CompressorDialog, LimiterDialog


class MainWindow(QMainWindow):
    level_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()

        self.audio = AudioEngine()

        self.selected_input = None
        self.selected_output = None

        self.level = 0
        self.smooth = 0
        self.smoothed = 0
        self.peak = 0

        self.output_history = deque(maxlen=8)
        self.output_smooth = 0

        self.level_signal.connect(self.update_level)

        self.setWindowTitle("Mic Effect Tester 1.0.2")
        self.resize(1100, 720)

        self.init_ui()
        self.audio.set_volume(50)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(50)

    def init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background:#111111;
                color:white;
                font-family:Segoe UI;
                font-size:14px;
            }

            QFrame#panel {
                background:#1b1b1b;
                border:1px solid #303030;
                border-radius:18px;
            }

            QPushButton {
                background:qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #222,
                    stop:1 #2d2d2d
                );
                border:1px solid #3c3c3c;
                border-radius:14px;
                padding:16px;
                font-size:18px;
                font-weight:600;
            }

            QScrollBar:vertical {
                background: #2b2b2b;
                width: 12px;
                margin: 2px 0px 2px 0px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical {
                background: #777777;
                min-height: 20px;
                border-radius: 6px;
            }

            QScrollBar::handle:vertical:hover {
                background: #999999;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }

            QPushButton:hover {
                border:1px solid #00cfff;
                color:#67e8ff;
            }

            QPushButton:pressed {
                background:#00a7d1;
            }

            QLabel#title {
                font-size:34px;
                font-weight:700;
                color:#63e6ff;
            }

            QLabel#section {
                font-size:16px;
                font-weight:700;
                color:#8befff;
            }

            QLabel#device {
                background:#101010;
                border:1px solid #3a3a3a;
                border-radius:10px;
                padding:10px;
                font-size:15px;
            }

            QProgressBar {
                border:1px solid #3a3a3a;
                border-radius:8px;
                background:#101010;
                text-align:right;
                height:30px;
                font-weight:bold;
            }

            QProgressBar::chunk {
                border-radius:7px;
                background:qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #114d18,
                    stop:0.4 #1e8f2e,
                    stop:0.8 #52d867,
                    stop:1 #9cff9c
                );
            }

            QSlider::groove:horizontal {
                background: #2b2b2b;
                height: 8px;
                border-radius: 4px;
            }

            QSlider::handle:horizontal {
                background: #00cfff;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }

            QSlider::handle:horizontal:hover {
                background: #67e8ff;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)

        main = QVBoxLayout(central)
        main.setContentsMargins(28, 28, 28, 28)
        main.setSpacing(22)

        title = QLabel("Mic Effect Tester")
        title.setObjectName("title")
        main.addWidget(title)

        # 頂部控制面板
        top = QFrame()
        top.setObjectName("panel")
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(24, 24, 24, 24)
        top_layout.setSpacing(18)

        # 輸入設備選單
        row1 = QHBoxLayout()
        row1.setSpacing(14)

        self.input_btn = QPushButton("Select Input Endpoint")
        self.input_btn.clicked.connect(self.select_input)
        self.input_btn.setFixedHeight(54)
        self.input_btn.setFixedWidth(240)

        self.input_label = QLabel("Not selected")
        self.input_label.setObjectName("device")
        self.input_label.setMinimumHeight(54)

        row1.addWidget(self.input_btn)
        row1.addWidget(self.input_label, 1)

        # 輸出設備選單
        row2 = QHBoxLayout()
        row2.setSpacing(14)

        self.output_btn = QPushButton("Select Output Endpoint")
        self.output_btn.clicked.connect(self.select_output)
        self.output_btn.setFixedHeight(54)
        self.output_btn.setFixedWidth(240)

        self.output_label = QLabel("Not selected")
        self.output_label.setObjectName("device")
        self.output_label.setMinimumHeight(54)

        row2.addWidget(self.output_btn)
        row2.addWidget(self.output_label, 1)

        # 音量指示器標籤
        meter_head = QHBoxLayout()

        meter_title = QLabel("INPUT VOLUME METER")
        meter_title.setObjectName("section")

        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("section")

        meter_head.addWidget(meter_title)
        meter_head.addStretch()
        meter_head.addWidget(self.percent_label)

        # 音量條
        self.input_bar = QProgressBar()
        self.input_bar.setRange(0, 100)
        self.input_bar.setTextVisible(False)

        # 音量控制項
        vol_head = QHBoxLayout()

        vol_title = QLabel("PLAYBACK VOLUME")
        vol_title.setObjectName("section")

        self.volume_label = QLabel("100%")
        self.volume_label.setObjectName("section")

        vol_head.addWidget(vol_title)
        vol_head.addStretch()
        vol_head.addWidget(self.volume_label)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.change_volume)

        top_layout.addLayout(row1)
        top_layout.addLayout(row2)
        top_layout.addLayout(meter_head)
        top_layout.addWidget(self.input_bar)
        top_layout.addSpacing(10)
        top_layout.addLayout(vol_head)
        top_layout.addWidget(self.volume_slider)

        main.addWidget(top)

        # 測試功能區
        effect_title = QLabel("Mic Effect Functions:")
        effect_title.setObjectName("title")
        effect_title.setStyleSheet("font-size:28px;color:#7cecff;")
        main.addWidget(effect_title)

        bottom = QHBoxLayout()
        bottom.setSpacing(18)

        btn1 = QPushButton("AINR")
        btn1.clicked.connect(self.open_ainr_test)

        btn2 = QPushButton("Compressor")
        btn2.clicked.connect(self.open_compressor_test)

        btn3 = QPushButton("Limiter")
        btn3.clicked.connect(self.open_limiter_test)

        btn1.setMinimumHeight(110)
        btn2.setMinimumHeight(110)
        btn3.setMinimumHeight(110)

        bottom.addWidget(btn1)
        bottom.addWidget(btn2)
        bottom.addWidget(btn3)

        main.addLayout(bottom)
        main.addStretch()

    def select_input(self): # 選擇輸入端點
        dlg = DeviceDialog(self.audio, True, self)
        if dlg.exec():
            self.selected_input = dlg.selected
            self.input_label.setText(self.selected_input["name"])
            print(f"Input device set: {self.selected_input['name']}")

            self.audio.start_input_meter(
                self.selected_input["id"],
                lambda v: self.level_signal.emit(v),
            )

    def select_output(self): # 選擇輸出端點
        dlg = DeviceDialog(self.audio, False, self)
        if dlg.exec():
            self.selected_output = dlg.selected
            self.output_label.setText(self.selected_output["name"])
            print(f"Output device set: {self.selected_output['name']}")

    def update_level(self, v):
        alpha = 0.3

        self.smooth = alpha * v + (1 - alpha) * self.smooth
        self.smoothed = self.smoothed * 0.85 + v * 0.15
        self.peak = max(self.peak * 0.95, v)

        self.output_history.append(v)

    def refresh(self):
        """刷新 UI 音量 meter"""
        value = int(self.smoothed)
        self.input_bar.setValue(value)
        self.percent_label.setText(f"{value}%")

    def closeEvent(self, event): # 視窗關閉清理
        try:
            print("Main window closing, resetting audio engine...")

            if self.refresh_timer.isActive():
                self.refresh_timer.stop()

            self.audio.stop_all_streams()

            self.audio.finished = False
            self.audio.noise_floor = None
            self.audio.playback_index = 0
            self.audio.test_audio_data = None
            self.audio.level_queue.clear()
            self.audio.audio_buffer.clear()

            self.audio.close()

        except Exception as e:
            print(f"[Error] Close error: {e}")
            traceback.print_exc()

        event.accept()

    def open_ainr_test(self):
        if self.selected_input is None or self.selected_output is None:
            QMessageBox.warning(
                self, "Notice", "Please select both Input and Output devices first."
            )
            return

        dlg = AINRDialog(
            self.audio, self.selected_input, self.selected_output, self
        )
        dlg.exec()

        if self.selected_input:
            self.audio.start_input_meter(
                self.selected_input["id"],
                lambda v: self.level_signal.emit(v),
            )

    def open_compressor_test(self):
        if self.selected_input is None or self.selected_output is None:
            QMessageBox.warning(
                self, "Notice", "Please select both Input and Output devices first."
            )
            return

        dlg = CompressorDialog(
            self.audio, self.selected_input, self.selected_output, self
        )
        dlg.exec()

        if self.selected_input:
            self.audio.start_input_meter(
                self.selected_input["id"],
                lambda v: self.level_signal.emit(v),
            )

    def open_limiter_test(self):
        if self.selected_input is None or self.selected_output is None:
            QMessageBox.warning(
                self, "Notice", "Please select both Input and Output devices first."
            )
            return

        dlg = LimiterDialog(
            self.audio, self.selected_input, self.selected_output, self
        )
        dlg.exec()

        if self.selected_input:
            self.audio.start_input_meter(
                self.selected_input["id"],
                lambda v: self.level_signal.emit(v),
            )

    def change_volume(self, value): # 調整播放音量
        self.audio.set_volume(value)

        if value <= 50:
            percent = int((value / 50) * 100)
        else:
            percent = int(100 + ((value - 50) / 50) * 400)

        self.volume_label.setText(f"{percent}%")


class DeviceDialog(QDialog):
    def __init__(self, audio, is_input=True, parent=None):
        super().__init__(parent)

        self.audio = audio
        self.is_input = is_input
        self.selected = None

        self.setWindowTitle(
            "Select Input Device" if is_input else "Select Output Device"
        )
        self.resize(540, 400)

        layout = QVBoxLayout(self)

        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(self.ok)
        layout.addWidget(self.listw)

        btn_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("Refresh Devices")
        self.refresh_btn.clicked.connect(self.refresh_devices)
        btn_layout.addWidget(self.refresh_btn)

        self.btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.btns.accepted.connect(self.ok)
        self.btns.rejected.connect(self.reject)
        btn_layout.addWidget(self.btns)

        layout.addLayout(btn_layout)

        self.refresh_devices()

    def refresh_devices(self):
        print(f"Refreshing {'Input' if self.is_input else 'Output'} devices...")

        self.audio.refresh_device_cache()

        self.listw.clear()
        self.devices = []

        ins, outs = self.audio.get_devices()
        self.devices = ins if self.is_input else outs

        for device in self.devices:
            self.listw.addItem(device["name"])

        if self.listw.count() > 0:
            self.listw.setCurrentRow(0)
            print(f"Loaded {self.listw.count()} device(s)")
        else:
            print("[Warning] No devices found")

    def ok(self): # 確認選擇設備
        i = self.listw.currentRow()
        if i >= 0 and i < len(self.devices):
            self.selected = self.devices[i]
            print(f"Selected: {self.selected['name']}")
            self.accept()
        else:
            QMessageBox.warning(self, "Warning", "Please select a valid device")


if __name__ == "__main__":
    try:
        utils.check_resources()

        app = QApplication(sys.argv)
        w = MainWindow()
        w.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"[Error] Fatal error: {e}")
        traceback.print_exc()