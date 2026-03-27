"""
中文语音输入 -> Claude Code (Linux / WSL)
按住 Right Alt 开始录音，松开结束，自动将识别文字粘贴到当前焦点窗口。
使用阿里 SenseVoiceSmall 模型。

Linux 原生 / WSL 均可使用。
- Linux 原生: 使用 evdev 监听键盘 + arecord 录音
- WSL: 使用 pynput 监听键盘 + sounddevice 录音

用法:
    python voice_input_linux.py              # 本地粘贴模式
    python voice_input_linux.py --host user@ip  # 远程 tmux 模式（SSH 发送）
"""

import sys
import re
import os
import threading
import queue
import subprocess
import tempfile
import argparse
import numpy as np

# ====== 配置 ======
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_SIZE = int(SAMPLE_RATE * 0.1)
MIN_DURATION = 0.3

# ====== 全局状态 ======
audio_queue = queue.Queue()
is_recording = False
model = None
is_wsl = "microsoft" in os.uname().release.lower() if hasattr(os, "uname") else False


def load_model():
    """加载 SenseVoiceSmall 模型"""
    global model
    if model is not None:
        return model

    # soundfile 补丁（兼容无 ffmpeg 环境）
    try:
        import torch
        import torchaudio
        import soundfile as sf

        def _sf_load(filepath, **kwargs):
            data, sr = sf.read(filepath, dtype="float32")
            if data.ndim == 1:
                data = data[np.newaxis, :]
            else:
                data = data.T
            return torch.from_numpy(data), sr

        torchaudio.load = _sf_load
    except Exception:
        pass

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
    """移除 SenseVoice 输出中的元数据标签"""
    text = re.sub(r"<\|[^|]*\|>", "", text)
    return text.strip()


def transcribe(audio_data):
    """使用 SenseVoiceSmall 识别音频"""
    import soundfile as sf

    m = load_model()

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        audio_float = audio_data.flatten().astype(np.float32)
        sf.write(tmp_path, audio_float, SAMPLE_RATE)

        result = m.generate(input=tmp_path, language="zh", use_itn=True)

        if result and result[0].get("text"):
            return clean_text(result[0]["text"])
        return ""
    finally:
        os.unlink(tmp_path)


# ====== 输出方式 ======

def paste_text_local(text):
    """本地粘贴模式：使用 xdotool 或 xclip 粘贴到当前窗口"""
    if not text:
        return
    try:
        # 优先用 xdotool type（适用于 X11 环境）
        subprocess.run(
            ["xdotool", "type", "--clearmodifiers", text],
            timeout=5,
        )
    except FileNotFoundError:
        # 退而用 xclip + xdotool key
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), timeout=5)
        subprocess.run(["xdotool", "key", "ctrl+v"], timeout=5)


def send_text_remote(text, host):
    """远程模式：通过 SSH 发送到远程 tmux session"""
    if not text:
        return
    try:
        # 获取最近活跃的 tmux session
        result = subprocess.run(
            ["ssh", host, "tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=10,
        )
        sessions = result.stdout.strip().split("\n")
        if not sessions or not sessions[0]:
            print("[error] 远程无 tmux session")
            return
        session = sessions[0]

        # 发送文字到 tmux（不自动回车，用户手动确认）
        escaped = text.replace("'", "'\\''")
        subprocess.run(
            ["ssh", host, f"tmux send-keys -t {session} '{escaped}'"],
            timeout=10,
        )
        print(f"[sent] -> {host} tmux:{session}")
    except Exception as e:
        print(f"[error] SSH 发送失败: {e}")


# ====== 录音方式 ======

def record_with_sounddevice():
    """使用 sounddevice 录音（WSL / 通用方案）"""
    import sounddevice as sd

    def audio_callback(indata, frames, time_info, status):
        if is_recording:
            audio_queue.put(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        callback=audio_callback,
        blocksize=BLOCK_SIZE,
    )
    stream.start()
    return stream


def record_with_arecord(tmp_path):
    """使用 arecord 录音（Linux 原生，更可靠）"""
    proc = subprocess.Popen(
        ["arecord", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", tmp_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


# ====== 键盘监听 ======

def use_evdev_listener(on_start, on_stop):
    """使用 evdev 监听键盘（Linux 原生，不需要 X11）"""
    import evdev
    from evdev import ecodes

    # 找到键盘设备
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    kbd = None
    for dev in devices:
        caps = dev.capabilities(verbose=False)
        if ecodes.EV_KEY in caps:
            kbd = dev
            break

    if kbd is None:
        print("[error] 未找到键盘设备，请确认用户已加入 input 组")
        sys.exit(1)

    print(f"[info] 键盘设备: {kbd.name}")
    RIGHT_ALT = ecodes.KEY_RIGHTALT

    for event in kbd.read_loop():
        if event.type == ecodes.EV_KEY and event.code == RIGHT_ALT:
            if event.value == 1:  # 按下
                on_start()
            elif event.value == 0:  # 松开
                on_stop()


def use_pynput_listener(on_start, on_stop):
    """使用 pynput 监听键盘（WSL / 通用方案）"""
    from pynput import keyboard
    from pynput.keyboard import Key

    def on_press(key):
        if key == Key.alt_r or key == Key.alt_gr:
            on_start()

    def on_release(key):
        if key == Key.alt_r or key == Key.alt_gr:
            on_stop()
        elif key == Key.esc:
            print("\n已退出。")
            os._exit(0)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener


# ====== 主程序 ======

def main():
    parser = argparse.ArgumentParser(description="中文语音输入 (Linux/WSL)")
    parser.add_argument("--host", help="远程服务器 user@ip（不填则本地粘贴模式）")
    parser.add_argument("--use-evdev", action="store_true", help="强制使用 evdev（需 input 组权限）")
    args = parser.parse_args()

    mode = "remote" if args.host else "local"
    use_evdev = args.use_evdev and not is_wsl

    print("=" * 50)
    print("  Chinese Voice Input (SenseVoiceSmall)")
    print(f"  模式: {'远程 -> ' + args.host if args.host else '本地粘贴'}")
    print(f"  环境: {'WSL' if is_wsl else 'Linux'}")
    print("  按住 Right Alt 说话，松开自动识别")
    print("  按 Esc 退出 | Ctrl+C 退出")
    print("=" * 50)

    load_model()

    # 录音流
    stream = record_with_sounddevice()

    def on_start():
        global is_recording
        if is_recording:
            return
        is_recording = True
        while not audio_queue.empty():
            audio_queue.get()
        print("[recording] 录音中... 松开 Right Alt 结束")

    def on_stop():
        global is_recording
        if not is_recording:
            return
        is_recording = False
        print("[processing] 识别中...")

        chunks = []
        while not audio_queue.empty():
            chunks.append(audio_queue.get())

        if not chunks:
            print("[warning] 未录到音频")
            return

        audio_data = np.concatenate(chunks, axis=0)
        duration = len(audio_data) / SAMPLE_RATE
        if duration < MIN_DURATION:
            print(f"[skip] 录音太短 ({duration:.1f}s)")
            return

        print(f"[info] 录音时长: {duration:.1f}s")

        def do_transcribe():
            text = transcribe(audio_data)
            if text:
                print(f"[result] {text}")
                if mode == "remote":
                    send_text_remote(text, args.host)
                else:
                    paste_text_local(text)
            else:
                print("[warning] 未识别到内容")

        threading.Thread(target=do_transcribe, daemon=True).start()

    # 键盘监听
    print("\n音频流已开启，等待语音输入...\n")

    if use_evdev:
        try:
            use_evdev_listener(on_start, on_stop)
        except KeyboardInterrupt:
            print("\n已退出。")
    else:
        listener = use_pynput_listener(on_start, on_stop)
        try:
            while listener.is_alive():
                listener.join(timeout=0.5)
        except KeyboardInterrupt:
            print("\n已退出。")
            listener.stop()

    stream.stop()


if __name__ == "__main__":
    main()
