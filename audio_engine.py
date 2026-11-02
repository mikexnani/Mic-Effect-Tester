# audio_engine.py
import threading
import time
import traceback
import uuid
from collections import deque

import numpy as np
import sounddevice as sd


class AudioEngine:
    def __init__(self):
        self.input_stream = None
        self.output_stream = None
        self.noise_floor = None
        self.level_queue = deque()
        self.audio_buffer = deque(maxlen=48000 * 10)
        self.finished = False
        self.lock = threading.Lock()

        self.test_audio_data = None
        self.playback_index = 0
        self.playback_thread = None

        self.volume_multiplier = 1.0

        self._active_test_id = None

    @staticmethod
    def clean_name(name): #清理特殊符號
        return (
            name.replace("®", "")
            .replace("™", "")
            .replace("(R)", "")
            .replace("(TM)", "")
            .strip()
        )

    def get_devices(self): # 列出系統 WASAPI 音訊端點
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()

            wasapi_index = None
            for i, api in enumerate(hostapis):
                if "WASAPI" in api["name"]:
                    wasapi_index = i
                    break

            inputs = []
            outputs = []
            seen_names = set()

            for i, dev in enumerate(devices):
                if dev["hostapi"] != wasapi_index:
                    continue

                name = self.clean_name(dev["name"])

                if dev["max_output_channels"] > 2 or dev["max_input_channels"] > 2:
                    continue

                if name in seen_names:
                    continue
                seen_names.add(name)

                if dev["max_input_channels"] > 0:
                    inputs.append({"id": i, "name": name})

                if dev["max_output_channels"] > 0:
                    outputs.append({"id": i, "name": name})

            print(
                f"[AudioEngine] WASAPI endpoints loaded: {len(inputs)} Inputs, {len(outputs)} Outputs"
            )
            return inputs, outputs

        except Exception as e:
            print(f"[Error] Failed to get devices: {e}")
            return [], []

    def _get_devices_sounddevice(self): # 讀取 sounddevice 預設裝置列表
        try:
            devices = sd.query_devices()
            inputs = []
            outputs = []

            if isinstance(devices, dict):
                devices = [devices]

            for i, dev in enumerate(devices):
                if not isinstance(dev, dict):
                    continue

                name = self.clean_name(dev.get("name", f"Device {i}"))
                max_input = dev.get("max_input_channels", 0)
                max_output = dev.get("max_output_channels", 0)

                if max_input > 0 and not any(d["name"] == name for d in inputs):
                    inputs.append({"id": i, "name": name})

                if max_output > 0 and not any(d["name"] == name for d in outputs):
                    outputs.append({"id": i, "name": name})

            return inputs, outputs
        except Exception as e:
            print(f"[Error] Failed to get sounddevice endpoints: {e}")
            return [], []

    def start_input_meter(self, device_id, callback): # 啟動輸入端音量監測
        self.stop_all_streams()
        self.noise_floor = None

        def audio_callback(indata, frames, time_info, status):
            try:
                if status:
                    print(f"[Warning] Input callback status: {status}")

                if indata is None or len(indata) == 0:
                    return

                audio = indata[:, 0] if indata.ndim > 1 else indata
                audio = (audio * 32768).astype(np.float32)

                with self.lock:
                    self.audio_buffer.append(audio.copy())

                rms = np.sqrt(np.mean(audio**2) + 1e-9)

                if self.noise_floor is None:
                    self.noise_floor = rms

                self.noise_floor = self.noise_floor * 0.995 + rms * 0.005

                if rms < self.noise_floor * 1.5:
                    level = 0
                else:
                    db = 20 * np.log10(rms + 1e-9)
                    db = np.clip(db, -60, 0)
                    norm = ((db + 60) / 60) ** 1.8
                    level = int(norm * 100)

                callback(level)

            except Exception as e:
                print(f"[Error] Input callback exception: {e}")

        try:
            self.input_stream = sd.InputStream(
                device=device_id,
                samplerate=48000,
                channels=1,
                blocksize=1024,
                callback=audio_callback,
            )
            self.input_stream.start()
        except Exception as e:
            print(f"[Error] Failed to start input meter: {e}")
            self.input_stream = None

    def _reset_runtime_state(self):
        self.finished = False
        self.noise_floor = None
        self.level_queue.clear()
        self.audio_buffer.clear()
        self.test_audio_data = None
        self.playback_index = 0

    def stop_all_streams(self, session_token=None):  # 停止並關閉目前所有的串流與線程
        with self.lock:
            if session_token is not None and self._active_test_id != session_token:
                return

            self._active_test_id = None
            self.finished = True

            if self.playback_thread and self.playback_thread.is_alive():
                try:
                    self.playback_thread.join(timeout=0.5)
                except Exception as e:
                    print(f"[Warning] Playback thread join timed out: {e}")
            self.playback_thread = None

            if self.input_stream:
                try:
                    self.input_stream.stop()
                    self.input_stream.close()
                except Exception as e:
                    print(f"[Warning] Failed to close input stream: {e}")
                self.input_stream = None

            if self.output_stream:
                try:
                    self.output_stream.stop()
                    self.output_stream.close()
                except Exception as e:
                    print(f"[Warning] Failed to close output stream: {e}")
                self.output_stream = None

            self.test_audio_data = None
            self.playback_index = 0
            self.level_queue.clear()
            self.audio_buffer.clear()
            time.sleep(0.15)

    def start_dual_test(self, input_device_id, output_device_id, audio_data, channels, session_token=None):
        test_id = session_token or uuid.uuid4().hex

        with self.lock:
            self._active_test_id = test_id
            self.finished = False
            self.noise_floor = None
            self.level_queue.clear()
            self.audio_buffer.clear()
            self.playback_index = 0
            self.test_audio_data = None

        audio_array = (
            np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        )

        if audio_array.size == 0:
            with self.lock:
                self.finished = True
            return

        if audio_array.ndim > 1:
            audio_array = audio_array.mean(axis=1)

        with self.lock:
            self.test_audio_data = audio_array
            self.playback_index = 0

        try:
            def output_callback(outdata, frames, time_info, status):
                try:
                    if status:
                        print(f"[Warning] Output status: {status}")

                    with self.lock:
                        if self._active_test_id != test_id:
                            outdata.fill(0)
                            return

                        if self.test_audio_data is None or self.playback_index >= len(self.test_audio_data):
                            outdata.fill(0)
                            return

                        data = self.test_audio_data
                        index = self.playback_index

                    frames_to_copy = min(frames, len(data) - index)

                    if frames_to_copy > 0:
                        chunk = data[index:index + frames_to_copy]
                        chunk = chunk * self.volume_multiplier
                        chunk = np.clip(chunk, -1.0, 1.0)
                        outdata[:frames_to_copy, 0] = chunk

                        with self.lock:
                            if self._active_test_id == test_id:
                                self.playback_index += frames_to_copy

                    if frames_to_copy < frames:
                        outdata[frames_to_copy:, 0] = 0

                except Exception as e:
                    print(f"[Error] Output callback error: {e}")
                    outdata.fill(0)

            def input_callback(indata, frames, time_info, status):
                try:
                    if status:
                        print(f"[Warning] Record status: {status}")

                    if indata is None or len(indata) == 0:
                        return

                    with self.lock:
                        if self._active_test_id != test_id:
                            return

                    audio = indata[:, 0] if indata.ndim > 1 else indata
                    audio_int = (audio * 32768).astype(np.float32)

                    with self.lock:
                        if self._active_test_id != test_id:
                            return
                        self.level_queue.append(audio_int.copy())
                        self.audio_buffer.append(audio_int.copy())

                    rms = np.sqrt(np.mean(audio_int**2) + 1e-9)
                    if self.noise_floor is None:
                        self.noise_floor = rms
                    self.noise_floor = self.noise_floor * 0.995 + rms * 0.005

                except Exception as e:
                    print(f"[Error] Input callback error: {e}")

            duration = len(self.test_audio_data) / 48000.0
            print(f"[AudioEngine] Starting output stream (device: {output_device_id}, duration: {duration:.2f}s)")

            self.output_stream = sd.OutputStream(
                device=output_device_id,
                samplerate=48000,
                channels=1,
                blocksize=1024,
                callback=output_callback,
            )
            self.output_stream.start()

            print(f"[AudioEngine] Starting input stream (device: {input_device_id})")
            self.input_stream = sd.InputStream(
                device=input_device_id,
                samplerate=48000,
                channels=1,
                blocksize=1024,
                callback=input_callback,
            )
            self.input_stream.start()

            def wait_for_playback():
                try:
                    playback_duration = len(self.test_audio_data) / 48000.0
                    time.sleep(playback_duration + 0.5)
                    time.sleep(0.5)

                    with self.lock:
                        if self._active_test_id == test_id:
                            self.finished = True

                    print("[AudioEngine] Playback finished")

                except Exception as e:
                    print(f"[Error] Playback wait interrupted: {e}")
                    with self.lock:
                        if self._active_test_id == test_id:
                            self.finished = True

            self.playback_thread = threading.Thread(target=wait_for_playback, daemon=True)
            self.playback_thread.start()

        except Exception as e:
            print(f"[Error] Failed to start dual test: {e}")
            traceback.print_exc()
            self.stop_all_streams(session_token=test_id)
            self.finished = True

    def close(self): # 釋放串流資源
        self.stop_all_streams()

    def refresh_device_cache(self): # 重設 PortAudio
        try:
            self.stop_all_streams()
            sd._terminate()
            sd._initialize()
            time.sleep(0.1)
            print("[AudioEngine] PortAudio device cache refreshed")
        except Exception as e:
            print(f"[Error] Refresh device cache failed: {e}")

    def set_volume(self, slider_value): # 設定增益倍率
        if slider_value <= 50:
            self.volume_multiplier = slider_value / 50.0
        else:
            self.volume_multiplier = 1.0 + ((slider_value - 50) / 50.0) * 4.0

        print(f"[AudioEngine] Gain multiplier updated: {self.volume_multiplier:.2f}x")