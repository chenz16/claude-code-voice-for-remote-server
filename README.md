# Claude Code Voice Input for Remote Servers

Voice input for [Claude Code](https://claude.ai/code) running on remote servers via SSH + tmux.

Hold **Right Alt** to speak, release to auto-transcribe and send text to your remote Claude Code session. Optimized for **Chinese speech recognition** using Alibaba's [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) model (`iic/SenseVoiceSmall` via [FunASR](https://github.com/modelscope/FunASR)).

## How It Works

```
[Host Machine]                          [Remote Server]
  Microphone                              tmux session
     │                                        ▲
     ▼                                        │
  arecord (capture audio)                     │
     │                                        │
     ▼                                        │
  SenseVoice (speech → text)                  │
     │                                        │
     └──── SSH tmux send-keys ────────────────┘
```

1. **Hold Right Alt** — starts recording audio via `arecord`
2. **Release Right Alt** — stops recording, transcribes with SenseVoice
3. Transcribed text is sent to the **most recently active tmux session** on the remote server
4. Text appears in the Claude Code input — **press Enter yourself** to confirm and send

## Features

- **Global hotkey** — works in any window (uses `evdev`, no X11 dependency)
- **Auto-detect tmux session** — always sends to your most recently active session
- **Model stays in memory** — first load takes a few seconds, subsequent transcriptions are fast
- **Runs as systemd service** — auto-starts on boot, runs in background
- **No auto-Enter** — text appears in input, you decide when to send

## Prerequisites

- **Host machine**: Linux with a microphone
- **Remote server**: SSH access with key-based auth, tmux running Claude Code
- **Python 3.10+** (tested with 3.12)

## Installation

### 1. Install system dependencies (on host)

```bash
sudo apt install alsa-utils
```

### 2. Install SenseVoice and Python dependencies (on host)

```bash
# Install FunASR (includes SenseVoice model support)
pip install funasr modelscope torch torchaudio

# Install evdev for global keyboard input
pip install evdev
```

The SenseVoice model (`iic/SenseVoiceSmall`, ~1GB) will be downloaded automatically on first run.

### 3. Add user to input group (on host)

Required for global keyboard hotkey to work:

```bash
sudo usermod -aG input $USER
```

**You must log out and log back in** for this to take effect.

### 4. Set up SSH key auth (on host)

```bash
ssh-copy-id user@remote-server-ip
```

### 5. Clone and run

```bash
git clone https://github.com/chenz16/claude-code-voice-for-remote-server.git
cd claude-code-voice-for-remote-server

# Test run
python3 voice_input.py --host user@remote-server-ip
```

### 6. (Optional) Install as systemd service for auto-start

Edit `setup_service.sh` to set your Python path, script path, and remote host, then:

```bash
bash setup_service.sh
```

This will:
- Create a systemd user service
- Enable it to start on boot
- Start it immediately

Manage the service:

```bash
# Check status
systemctl --user status voice-input.service

# View logs
journalctl --user -u voice-input.service -f

# Restart
systemctl --user restart voice-input.service

# Stop
systemctl --user stop voice-input.service
```

## Usage

```
python3 voice_input.py --host user@remote-ip
```

```
Testing SSH to user@remote-ip...
SSH OK.
  Available sessions: dev, main, test
Loading SenseVoice model...
Model loaded and ready!

=== Voice Input for Claude Code ===
  Remote: user@remote-ip
  Auto-detects active tmux session each time.
  Hold RIGHT ALT to record, release to stop. (global, any window)
  Text appears in tmux — press Enter yourself to confirm.
```

## About SenseVoice

This project uses [SenseVoice](https://github.com/FunAudioLLM/SenseVoice) by Alibaba's FunAudioLLM team, specifically the `iic/SenseVoiceSmall` model via the [FunASR](https://github.com/modelscope/FunASR) framework.

SenseVoice is a speech foundation model with excellent Chinese speech recognition accuracy, supporting:
- Mandarin Chinese (optimized)
- Cantonese, English, Japanese, Korean
- Inverse text normalization (punctuation, numbers)
- Emotion recognition and audio event detection

## License

MIT
