# Claude Code Voice Input — Mandarin Speech Recognition

Hold **Right Alt** to speak Mandarin, release to auto-transcribe and input. Powered by Alibaba's [SenseVoiceSmall](https://github.com/FunAudioLLM/SenseVoice) model — state-of-the-art Mandarin speech recognition accuracy, significantly better than Whisper.

---

## Use Cases

### Use Case 1: Linux Host → Remote Server (SSH + tmux)

```
┌─────────────────────────┐        SSH         ┌─────────────────────┐
│     Linux Host Machine   │ ────────────────── │  Remote GPU Server   │
│                           │                   │                      │
│  🎤 Microphone            │                   │  tmux session        │
│  ↓                        │                   │    ↑                 │
│  arecord (capture audio)  │                   │    │                 │
│  ↓                        │                   │    │                 │
│  SenseVoice (speech→text) │  ── send-keys ──> │  Claude Code input   │
│                           │                   │                      │
│  Hold Right Alt to speak  │                   │  Text appears, press │
│  Release to transcribe    │                   │  Enter to confirm    │
└─────────────────────────┘                     └─────────────────────┘
```

**Scenario**: You work on a Linux desktop/laptop. Claude Code runs on a remote GPU server inside a tmux session. Audio is captured and transcribed locally; the result is sent to the remote tmux session via SSH.

**Script**: `voice_input.py`

```bash
python3 voice_input.py --host user@remote-server-ip
```

### Use Case 2: Windows → Local Window (Claude Code / Any App)

```
┌──────────────────────────────────────────────┐
│                 Windows 11                     │
│                                                │
│  🎤 Microphone                                 │
│  ↓                                             │
│  sounddevice (capture audio)                   │
│  ↓                                             │
│  SenseVoice (speech → text)                    │
│  ↓                                             │
│  Ctrl+V paste into focused window              │
│                                                │
│  ┌────────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Claude Code │ │ Browser  │ │ Text Editor  │ │
│  └────────────┘ └──────────┘ └──────────────┘ │
│                                                │
│  Hold Right Alt to speak, release to paste     │
└──────────────────────────────────────────────┘
```

**Scenario**: You use Claude Code (or any app) directly on Windows. Audio is captured and transcribed locally; the result is pasted into whichever window has focus.

**Script**: `voice_input_win.py`

```powershell
python voice_input_win.py
```

---

## Installation

### Use Case 1: Linux → Remote Server

```bash
# System dependencies
sudo apt install alsa-utils

# Python dependencies
pip install funasr modelscope torch torchaudio evdev

# Add user to input group (required for evdev global keyboard listener)
sudo usermod -aG input $USER
# Log out and log back in for this to take effect

# Set up SSH key auth (passwordless login)
ssh-copy-id user@remote-server-ip

# Run
python3 voice_input.py --host user@remote-server-ip
```

#### Optional: Auto-start as systemd service

Edit `setup_service.sh` to set your Python path, script path, and remote host, then:

```bash
bash setup_service.sh
```

Manage the service:

```bash
systemctl --user status voice-input.service      # Check status
journalctl --user -u voice-input.service -f       # View logs
systemctl --user restart voice-input.service      # Restart
systemctl --user stop voice-input.service         # Stop
```

### Use Case 2: Windows Local

```powershell
# Install Python 3.11+ (if not installed)
winget install Python.Python.3.11

# Install dependencies
pip install -r requirements_win.txt

# Run
python voice_input_win.py
```

> **Note**: If the `python` command opens Microsoft Store instead of running Python, go to
> **Settings > Apps > Advanced app settings > App execution aliases** and turn off `python.exe` and `python3.exe`.

---

## Usage

1. Run the script (first run downloads the ~1GB model)
2. **Switch to the target window** (Claude Code, terminal, browser, etc.)
3. **Hold Right Alt** and speak Mandarin
4. **Release** → auto-transcribe and input
5. **Esc** or **Ctrl+C** to exit

---

## Files

| File | Platform | Description |
|------|----------|-------------|
| `voice_input.py` | Linux | SSH remote mode — sends text to tmux session on remote server |
| `voice_input_win.py` | Windows | Local mode — pastes text into focused window via clipboard |
| `voice_input_linux.py` | Linux / WSL | Local paste + optional remote mode |
| `setup_service.sh` | Linux | systemd service installer for auto-start on boot |
| `requirements_win.txt` | Windows | Python dependencies |
| `requirements_linux.txt` | Linux | Python dependencies |
| `setup.bat` | Windows | One-click dependency installer |

---

## Speech Model

This project uses [SenseVoiceSmall](https://github.com/FunAudioLLM/SenseVoice) by Alibaba's FunAudioLLM team:

- **Best-in-class Mandarin** (+ Cantonese) speech recognition
- Also supports English, Japanese, Korean
- Inverse text normalization (spoken numbers → digits, punctuation insertion)
- ~1GB model, runs fully offline — no API key or internet needed after download

## License

MIT
