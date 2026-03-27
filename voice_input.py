#!/usr/bin/env python3
"""
Voice input for Claude Code on remote servers.
Hold RIGHT ALT to record, release to stop and auto-transcribe.
Uses Alibaba SenseVoice (FunASR/SenseVoiceSmall) — optimized for Chinese speech recognition.
Uses evdev for global keyboard input (no X11 dependency, works as systemd service).
Auto-detects the most recently active tmux session on remote and sends text there.

Usage:
  python3 voice_input.py
  python3 voice_input.py --host user@remote-ip

Dependencies:
  pip install funasr modelscope evdev
  sudo apt install alsa-utils
  User must be in 'input' group: sudo usermod -aG input $USER
"""

import os
import subprocess
import signal
import threading
import re
import time
import argparse
import evdev
from evdev import ecodes
from funasr import AutoModel

TMPWAV = "/tmp/whisper_input.wav"

recording = False
record_proc = None
lock = threading.Lock()
model = None
args = None


def clean_text(text):
    """Remove SenseVoice emotion/event tags like <|zh|><|EMO|><|Event|>"""
    return re.sub(r"<\|[^|]*\|>", "", text).strip()


def get_active_session():
    """Auto-detect the most recently active tmux session on remote."""
    ret = subprocess.run(
        ["ssh", args.host,
         "tmux list-clients -F '#{client_activity} #{session_name}' 2>/dev/null | sort -rn | head -1 | awk '{print $2}'"],
        capture_output=True, text=True,
    )
    session = ret.stdout.strip()
    if session:
        return session
    ret = subprocess.run(
        ["ssh", args.host,
         "tmux list-sessions -F '#{session_activity} #{session_name}' 2>/dev/null | sort -rn | head -1 | awk '{print $2}'"],
        capture_output=True, text=True,
    )
    return ret.stdout.strip() or None


def send_to_remote(text, session):
    """Send text to remote tmux session via SSH (no auto Enter)."""
    escaped = text.replace("\\", "\\\\").replace("'", "'\\''").replace(";", "\\;")
    cmd = f"ssh {args.host} \"tmux send-keys -t {session} '{escaped}'\""
    subprocess.run(cmd, shell=True, capture_output=True)


def start_recording():
    global record_proc, recording
    with lock:
        if recording:
            return
        recording = True
    print("\n  Recording... (release RIGHT ALT to stop)", flush=True)
    record_proc = subprocess.Popen(
        ["arecord", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "wav", TMPWAV],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_recording():
    global record_proc, recording
    with lock:
        if not recording:
            return
        recording = False
    if record_proc:
        record_proc.send_signal(signal.SIGINT)
        record_proc.wait()
        record_proc = None
    print("  Stopped. Transcribing...", flush=True)
    transcribe()


def transcribe():
    try:
        if not os.path.exists(TMPWAV):
            print("  No audio file found.", flush=True)
            return

        result = model.generate(input=TMPWAV, language="zh", use_itn=True)
        text = clean_text(result[0]["text"])

        if not text:
            print("  No speech detected.", flush=True)
            return

        print(f"\n  >>> {text}", flush=True)

        session = get_active_session()
        if not session:
            print("  ERROR: No active tmux session found on remote.", flush=True)
            return

        print(f"  -> tmux:{session}", flush=True)
        send_to_remote(text, session)
        print("  Sent!", flush=True)

    except Exception as e:
        print(f"  Error: {e}", flush=True)
    finally:
        if os.path.exists(TMPWAV):
            os.remove(TMPWAV)
    print("\n  Hold RIGHT ALT to record again...", flush=True)


def find_keyboard():
    """Find the first keyboard device."""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for dev in devices:
        caps = dev.capabilities(verbose=False)
        if ecodes.EV_KEY in caps:
            keys = caps[ecodes.EV_KEY]
            if ecodes.KEY_SPACE in keys and ecodes.KEY_A in keys:
                print(f"  Keyboard: {dev.name} ({dev.path})", flush=True)
                return dev
    return None


def keyboard_loop(dev):
    """Main loop reading keyboard events via evdev."""
    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        key_event = evdev.categorize(event)

        if key_event.scancode == ecodes.KEY_RIGHTALT:
            if key_event.keystate == key_event.key_down:
                if not recording:
                    start_recording()
            elif key_event.keystate == key_event.key_up:
                if recording:
                    threading.Thread(target=stop_recording, daemon=True).start()


def main():
    global model, args

    parser = argparse.ArgumentParser(
        description="Voice input for Claude Code on remote servers. "
        "Uses Alibaba SenseVoice for Chinese speech recognition."
    )
    parser.add_argument("--host", required=True, help="SSH host (e.g. user@remote-ip)")
    args = parser.parse_args()

    for cmd in ["arecord", "ssh"]:
        if subprocess.run(["which", cmd], capture_output=True).returncode != 0:
            print(f"ERROR: '{cmd}' not found.")
            exit(1)

    # Test SSH connection
    print(f"Testing SSH to {args.host}...", flush=True)
    ret = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", args.host, "echo ok"],
        capture_output=True, text=True,
    )
    if ret.returncode != 0:
        print(f"ERROR: Cannot SSH to {args.host}. Set up SSH key auth first.")
        exit(1)
    print("SSH OK.", flush=True)

    # List available tmux sessions
    ret = subprocess.run(
        ["ssh", args.host, "tmux list-sessions -F '#{session_name}' 2>/dev/null"],
        capture_output=True, text=True,
    )
    sessions = ret.stdout.strip()
    if sessions:
        print(f"  Available sessions: {', '.join(sessions.splitlines())}", flush=True)

    # Find keyboard
    dev = find_keyboard()
    if not dev:
        print("ERROR: No keyboard found. Make sure user is in 'input' group.", flush=True)
        print("  Run: sudo usermod -aG input $USER", flush=True)
        exit(1)

    print("Loading SenseVoice model...", flush=True)
    model = AutoModel(model="iic/SenseVoiceSmall", trust_remote_code=True, disable_update=True)
    print("Model loaded and ready!", flush=True)
    print("")
    print("=== Voice Input for Claude Code ===")
    print(f"  Remote: {args.host}")
    print("  Auto-detects active tmux session each time.")
    print("  Hold RIGHT ALT to record, release to stop. (global, any window)")
    print("  Text appears in tmux — press Enter yourself to confirm.")
    print("", flush=True)

    keyboard_loop(dev)


if __name__ == "__main__":
    main()
