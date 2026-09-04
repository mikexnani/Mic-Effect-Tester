import os
import sys
import wave
import numpy as np


def resource_path(relative_path): # 取得相對路徑
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# 資源檔案路徑配置
AINRwav_path = resource_path(os.path.join("resources", "AINR_Test.wav"))
Limiterwav_path = resource_path(os.path.join("resources", "Limiter_Test.wav"))
Compressorwav_path = resource_path(
    os.path.join("resources", "Compressor_Test.wav")
)


def check_resources(): # 驗證必要資源檔案是否存在且可讀取
    missing_files = []
    for p in [AINRwav_path, Limiterwav_path, Compressorwav_path]:
        if not os.path.exists(p):
            missing_files.append(p)

    if missing_files:
        print("-" * 30)
        print("[Error] Resource files missing:")
        for f in missing_files:
            print(f"Missing: {f}")

        try:
            base_dir = os.path.dirname(AINRwav_path)
            print(f"\nSearch path: {base_dir}")
            print(f"Directory content: {os.listdir(base_dir)}")
        except Exception as e:
            print(f"Failed to inspect directory: {e}")

        print("-" * 30)
        input("Press Enter to exit...")
        sys.exit(1)

    try:
        with wave.open(AINRwav_path) as wf1:
            pass
        with wave.open(Limiterwav_path) as wf2:
            pass
        with wave.open(Compressorwav_path) as wf3:
            pass
        print("Audio resources validated successfully.")
    except Exception as e:
        print(f"[Error] Failed to validate audio files: {e}")
        input("Press Enter to exit...")
        sys.exit(1)


def load_audio_file(wav_path): #讀取WAV，雙聲道轉為單聲道
    try:
        with wave.open(wav_path) as wf:
            data = wf.readframes(wf.getnframes())
            channels = wf.getnchannels()

        if channels == 2:
            audio = np.frombuffer(data, dtype=np.int16)
            audio = audio.reshape(-1, 2)
            audio = audio.mean(axis=1).astype(np.int16)
            data = audio.tobytes()

        return data
    except Exception as e:
        print(f"[Error] Failed to load {wav_path}: {e}")
        return None