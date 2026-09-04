# widgets.py 自訂 UI 元件模組

import threading
import time
import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class WaveformWidget(QWidget):

    def __init__(self, duration_seconds=5, sample_rate=48000, track_type="default"):
        super().__init__()
        self.duration_seconds = duration_seconds
        self.sample_rate = sample_rate
        self.max_samples = duration_seconds * sample_rate
        self.data = np.zeros(self.max_samples, dtype=np.float32)
        self.current_index = 0
        self.recording = False
        self.lock = threading.Lock()
        self.recording_start_time = None
        self.audio_start_index = 0

        self.track_type = track_type

        if track_type == "limiter_track1":
            self.waveform_color = Qt.GlobalColor.green
            self.label = "Track 1"
        elif track_type == "limiter_track2":
            self.waveform_color = Qt.GlobalColor.cyan
            self.label = "Track 2"
        elif track_type == "ainr_track1":
            self.waveform_color = Qt.GlobalColor.green
            self.label = "Track 1"
        elif track_type == "ainr_track2":
            self.waveform_color = Qt.GlobalColor.cyan
            self.label = "Track 2"
        elif track_type == "compressor_track1":
            self.waveform_color = Qt.GlobalColor.green
            self.label = "Track 1"
        elif track_type == "compressor_track2":
            self.waveform_color = Qt.GlobalColor.cyan
            self.label = "Track 2"
        else:
            self.waveform_color = Qt.GlobalColor.green
            self.label = "Recording"

    def start_recording(self, audio_start_index=0): # 開始錄音並初始化數據緩衝區
        with self.lock:
            self.data = np.zeros(self.max_samples, dtype=np.float32)
            self.current_index = 0
            self.recording = True
            self.recording_start_time = time.time()
            self.audio_start_index = audio_start_index
        self.update()

    def stop_recording(self): #停止錄音
        with self.lock:
            self.recording = False

    def append_data(self, chunk): #追加音訊數據至緩衝區
        if chunk is None or len(chunk) == 0:
            return

        with self.lock:
            if not self.recording or self.recording_start_time is None:
                return

            try:
                chunk_array = np.array(chunk, dtype=np.float32)
                chunk_len = len(chunk_array)

                remaining = self.max_samples - self.current_index
                write_len = min(chunk_len, remaining)

                if write_len > 0:
                    self.data[self.current_index:self.current_index + write_len] = chunk_array[:write_len]
                    self.current_index += write_len

            except Exception as e:
                print(f"[Error] Failed to append waveform data: {e}")

        self.update()

    def clear_data(self): #重置錄音狀態與繪製數據
        with self.lock:
            self.data = np.zeros(self.max_samples, dtype=np.float32)
            self.current_index = 0
            self.recording = False
            self.recording_start_time = None
            self.audio_start_index = 0
        self.update()

    def get_progress(self): # 計算目前錄音進度比例 (0.0 - 1.0)
        with self.lock:
            return self.current_index / self.max_samples

    def paintEvent(self, event): # 繪製即時波形與參考線
        painter = QPainter(self)

        w = self.width()
        h = self.height()

        painter.fillRect(self.rect(), Qt.GlobalColor.black)

        painter.setPen(QPen(Qt.GlobalColor.darkGray, 1))
        painter.drawLine(0, h // 2, w, h // 2)

        if self.track_type in [
            "limiter_track1", "limiter_track2",
            "ainr_track1", "ainr_track2",
            "compressor_track1", "compressor_track2"
        ]:
            limiter_line_y = h // 6
            painter.setPen(QPen(Qt.GlobalColor.darkGray, 1))
            painter.drawLine(0, limiter_line_y, w, limiter_line_y)
            painter.drawLine(0, h - limiter_line_y, w, h - limiter_line_y)

        with self.lock:
            if self.current_index > 0:
                color = QColor(self.waveform_color)
                color.setAlpha(int(255 * 0.5))
                painter.setPen(QPen(color, 1))

                samples_per_pixel = max(1, self.max_samples // w)
                max_pixel = int((self.current_index / self.max_samples) * w) + 1
                max_pixel = min(max_pixel, w)

                for i in range(max_pixel):
                    start_idx = i * samples_per_pixel
                    end_idx = min(start_idx + samples_per_pixel, self.current_index)

                    if start_idx >= self.current_index:
                        break

                    chunk = self.data[start_idx:end_idx]

                    if len(chunk) > 0:
                        v = np.max(np.abs(chunk)) / 32768.0
                        v = min(v, 1.0)
                        y = int(v * h / 2)

                        if y > 0:
                            painter.drawLine(i, h // 2 - y, i, h // 2 + y)

        progress = self.get_progress()
        current_x = int(w * progress)
        painter.setPen(QPen(Qt.GlobalColor.yellow, 2))
        painter.drawLine(current_x, 0, current_x, h)