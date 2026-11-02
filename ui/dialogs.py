# dialogs.py
import time
import traceback
import uuid

import sounddevice as sd

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

import utils
from audio_engine import AudioEngine
from ui.widgets import WaveformWidget


class BaseTestDialog(QDialog): #彈出視窗類別
    def __init__(
        self,
        audio,
        in_dev,
        out_dev,
        title_text,
        wav_path,
        track1_type,
        track2_type,
        track1_label="Track 1: Initial Recording",
        track2_label="Track 2: Comparison Recording",
        window_height=450,
        parent=None,
    ):
        super().__init__(parent)

        # 每個 dialog 保持自己的 engine
        self.audio = audio if audio is not None else AudioEngine()

        self.in_dev = in_dev
        self.out_dev = out_dev
        self.wav_path = wav_path
        self.test_count = 0
        self.test_session_id = uuid.uuid4().hex

        self.setWindowTitle(title_text)
        self.setFixedSize(700, window_height)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_audio)

        layout = QVBoxLayout(self)

        title = QLabel(title_text)
        title.setStyleSheet("font-size:28px; font-weight:700; color:#63e6ff;")
        layout.addWidget(title)

        layout.addWidget(QLabel(track1_label)) # Track 1 波形圖
        self.track1 = WaveformWidget(
            duration_seconds=5 if "limiter" not in track1_type else 3,
            sample_rate=48000,
            track_type=track1_type,
        )
        self.track1.setMinimumHeight(100)
        layout.addWidget(self.track1)

        layout.addWidget(QLabel(track2_label)) # Track 2 波形圖
        self.track2 = WaveformWidget(
            duration_seconds=5 if "limiter" not in track2_type else 3,
            sample_rate=48000,
            track_type=track2_type,
        )
        self.track2.setMinimumHeight(100)
        layout.addWidget(self.track2)

        layout.addStretch()

        btn_layout = QVBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setFixedHeight(60)
        warn_label = QLabel("Attention: Please mind the volume")
        warn_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        warn_label.setStyleSheet("font-size: 12px; color: #f73131;")

        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(warn_label)
        layout.addLayout(btn_layout)

        self.start_btn.clicked.connect(self.run_test_flow)

    def run_test_flow(self): #第一輪test run
        if self.timer.isActive():
            return

        if not self.in_dev or not self.out_dev:
            QMessageBox.warning(
                self, "Error", "Please select Input/Output first on Main Page"
            )
            return

        self.start_btn.setEnabled(False)

        data = utils.load_audio_file(self.wav_path)
        if data is None:
            self.start_btn.setEnabled(True)
            return

        self.test_count = 1
        self.track1.clear_data()
        self.track2.clear_data()
        self.track1.start_recording(audio_start_index=0)

        self.audio.start_dual_test(
            self.in_dev["id"],
            self.out_dev["id"],
            data,
            1,
            session_token=self.test_session_id,
        )
        self.timer.start(30)

    def first_done(self):
        QTimer.singleShot(0, self.show_continue)

    def show_continue(self): # 第一輪完成提示
        msg = QMessageBox(self)
        msg.setWindowTitle("Continue")
        msg.setText("First record finished. Continue?")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)

        if msg.exec() == QMessageBox.StandardButton.Ok:
            QTimer.singleShot(300, self.run_second)

    def run_second(self): #第二輪test run
        self.test_count = 2
        delay_samples = int(0.3 * 48000)

        self.audio.stop_all_streams(self.test_session_id)
        time.sleep(0.3)

        self.audio.finished = False
        self.audio.noise_floor = None

        self.track1.stop_recording()
        self.track2.clear_data()
        self.track2.start_recording(audio_start_index=delay_samples)

        sd.default.samplerate = None
        sd.default.channels = None
        time.sleep(0.1)

        data = utils.load_audio_file(self.wav_path)
        if data is None:
            self.start_btn.setEnabled(True)
            return

        self.audio.start_dual_test(
            self.in_dev["id"],
            self.out_dev["id"],
            data,
            1,
            session_token=self.test_session_id,
        )
        self.timer.start(30)

    def test_finished(self):
        QTimer.singleShot(0, self.show_finish_dialog)

    def show_finish_dialog(self): # 第二輪完成提示
        msg = QMessageBox(self)
        msg.setWindowTitle("Recording Complete")
        msg.setText("Recording finished successfully!")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
        self.start_btn.setEnabled(True)

    def poll_audio(self):
        with self.audio.lock:
            while self.audio.level_queue:
                chunk = self.audio.level_queue.popleft()
                if self.test_count == 1:
                    self.track1.append_data(chunk)
                elif self.test_count == 2:
                    self.track2.append_data(chunk)

        if self.audio.finished:
            self.timer.stop()
            if self.test_count == 1:
                self.track1.stop_recording()
            else:
                self.track2.stop_recording()

            self.audio.stop_all_streams(self.test_session_id)
            self.audio.finished = False

            if self.test_count == 1:
                self.first_done()
            else:
                self.test_finished()

    def closeEvent(self, event): # 視窗關閉重置狀態
        try:
            print(f"[Dialog] {self.windowTitle()} closing, resetting audio engine...")
            if self.timer.isActive():
                self.timer.stop()

            self.audio.stop_all_streams(self.test_session_id)

            self.audio.finished = False
            self.audio.noise_floor = None
            self.audio.playback_index = 0
            self.audio.test_audio_data = None
            self.audio.level_queue.clear()
            self.audio.audio_buffer.clear()

            self.track1.clear_data()
            self.track2.clear_data()
        except Exception as e:
            print(f"[Error] Dialog close error: {e}")
            traceback.print_exc()

        event.accept()


class AINRDialog(BaseTestDialog):
    def __init__(self, audio, in_dev, out_dev, parent=None):
        super().__init__(
            audio=audio,
            in_dev=in_dev,
            out_dev=out_dev,
            title_text="AINR Performance Test",
            wav_path=utils.AINRwav_path,
            track1_type="ainr_track1",
            track2_type="ainr_track2",
            window_height=450,
            parent=parent,
        )


class CompressorDialog(BaseTestDialog):
    def __init__(self, audio, in_dev, out_dev, parent=None):
        super().__init__(
            audio=audio,
            in_dev=in_dev,
            out_dev=out_dev,
            title_text="Compressor Performance Test",
            wav_path=utils.Compressorwav_path,
            track1_type="compressor_track1",
            track2_type="compressor_track2",
            window_height=500,
            parent=parent,
        )


class LimiterDialog(BaseTestDialog):
    def __init__(self, audio, in_dev, out_dev, parent=None):
        super().__init__(
            audio=audio,
            in_dev=in_dev,
            out_dev=out_dev,
            title_text="Limiter Performance Test",
            wav_path=utils.Limiterwav_path,
            track1_type="limiter_track1",
            track2_type="limiter_track2",
            track1_label="Track 1: Initial Recording (OFF)",
            track2_label="Track 2: Comparison Recording (ON)",
            window_height=450,
            parent=parent,
        )