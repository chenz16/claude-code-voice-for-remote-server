"""
中文语音输入 -> Claude Code 无缝集成 (Windows 版)
按住 Right Alt 开始录音，松开结束，自动将识别文字粘贴到当前焦点窗口。
使用阿里 SenseVoiceSmall 模型，中文识别精度优于 Whisper。
"""

import sys
import re
import threading
import queue
import tempfile
import os
import time
import numpy as np
import sounddevice as sd
import pyperclip
from pynput import keyboard
from pynput.keyboard import Key, Controller

# ====== 配置 ======
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = int(SAMPLE_RATE * 0.1)  # 100ms per block
MIN_DURATION = 0.3                    # 最短录音时长（秒）

# ====== 全局状态 ======
audio_queue = queue.Queue()
is_recording = False
model = None
kb_controller = Controller()


def load_model():
    """加载 SenseVoiceSmall 模型（首次运行需下载 ~1GB）"""
    global model
    if model is not None:
        return model
    # 猴子补丁：用 soundfile 替换 torchaudio.load（Windows 无 ffmpeg/torchcodec）
    import torch
    import torchaudio
    import soundfile as sf

    def _sf_load(filepath, **kwargs):
        data, sr = sf.read(filepath, dtype="float32")
        if data.ndim == 1:
            data = data[np.newaxis, :]  # [1, T]
        else:
            data = data.T  # [C, T]
        return torch.from_numpy(data), sr

    torchaudio.load = _sf_load
    print("正在加载 SenseVoiceSmall 语音模型...")
    print("(首次运行需从 ModelScope 下载 ~1GB，请耐心等待)")
    from funasr import AutoModel
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        trust_remote_code=True,
    )
    print("模型加载完成！")
    return model


def clean_text(text):
    """移除 SenseVoice 输出中的元数据标签，如 <|zh|><|NEUTRAL|> 等"""
    text = re.sub(r"<\|[^|]*\|>", "", text)
    return text.strip()


def audio_callback(indata, frames, time_info, status):
    """录音回调，将音频数据放入队列"""
    if is_recording:
        audio_queue.put(indata.copy())


def transcribe(audio_data):
    """使用 SenseVoiceSmall 识别音频"""
    import soundfile as sf

    m = load_model()

    # 用 soundfile 写 wav，再让 FunASR 用 soundfile 读（绕过 torchaudio/ffmpeg）
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        audio_float = audio_data.flatten().astype(np.float32)
        sf.write(tmp_path, audio_float, SAMPLE_RATE)

        result = m.generate(
            input=tmp_path,
            language="zh",
            use_itn=True,
        )

        if result and result[0].get("text"):
            return clean_text(result[0]["text"])
        return ""
    finally:
        os.unlink(tmp_path)


def paste_text(text):
    """将文字粘贴到当前焦点窗口，完成后恢复剪贴板"""
    if not text:
        return
    old_clipboard = ""
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    pyperclip.copy(text)
    time.sleep(0.05)
    kb_controller.press(Key.ctrl)
    kb_controller.press("v")
    kb_controller.release("v")
    kb_controller.release(Key.ctrl)
    time.sleep(0.1)

    # 恢复原剪贴板内容
    try:
        pyperclip.copy(old_clipboard)
    except Exception:
        pass


def start_recording():
    """开始录音"""
    global is_recording
    if is_recording:
        return
    is_recording = True
    # 清空队列
    while not audio_queue.empty():
        audio_queue.get()
    print("[recording] 录音中... 松开 Right Alt 结束")


def stop_recording():
    """停止录音并识别"""
    global is_recording
    if not is_recording:
        return
    is_recording = False
    print("[processing] 识别中...")

    # 收集录音数据
    chunks = []
    while not audio_queue.empty():
        chunks.append(audio_queue.get())

    if not chunks:
        print("[warning] 未录到音频")
        return

    audio_data = np.concatenate(chunks, axis=0)
    duration = len(audio_data) / SAMPLE_RATE
    if duration < MIN_DURATION:
        print(f"[skip] 录音太短 ({duration:.1f}s)，跳过")
        return

    print(f"[info] 录音时长: {duration:.1f}s")

    # 在后台线程识别，避免阻塞键盘监听
    def do_transcribe():
        text = transcribe(audio_data)
        if text:
            print(f"[result] {text}")
            paste_text(text)
        else:
            print("[warning] 未识别到内容")

    threading.Thread(target=do_transcribe, daemon=True).start()


def main():
    print("=" * 50)
    print("  Chinese Voice Input (SenseVoiceSmall)")
    print("  按住 Right Alt 说话，松开自动识别并粘贴")
    print("  按 Esc 退出")
    print("=" * 50)

    # 预加载模型
    load_model()

    # 键盘监听
    def on_press(key):
        if key == Key.alt_r or key == Key.alt_gr:
            start_recording()

    def on_release(key):
        if key == Key.alt_r or key == Key.alt_gr:
            stop_recording()
        elif key == Key.esc:
            print("\n已退出。")
            os._exit(0)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    # 开启音频流（持续运行，只在 is_recording=True 时收集数据）
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        callback=audio_callback,
        blocksize=BLOCK_SIZE,
    ):
        print("\n音频流已开启，等待语音输入...\n")
        try:
            while listener.is_alive():
                listener.join(timeout=0.5)
        except KeyboardInterrupt:
            print("\n已退出。")
            listener.stop()


if __name__ == "__main__":
    main()
