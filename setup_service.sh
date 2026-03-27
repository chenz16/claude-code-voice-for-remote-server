#!/bin/bash
# Setup voice-input as a systemd user service (auto-start on boot)
#
# Usage:
#   1. Edit PYTHON_PATH and SCRIPT_PATH below to match your system
#   2. Edit --host in ExecStart to match your remote server
#   3. Run: bash setup_service.sh

PYTHON_PATH="$HOME/miniconda3/bin/python3"   # Change to your python path
SCRIPT_PATH="$HOME/project/whisper/voice_input.py"  # Change to where you put voice_input.py
REMOTE_HOST="user@remote-ip"  # Change to your remote SSH host

# Get user UID for XDG_RUNTIME_DIR
USER_ID=$(id -u)

mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/voice-input.service << EOF
[Unit]
Description=Voice Input for Claude Code
After=graphical-session.target

[Service]
ExecStart=${PYTHON_PATH} ${SCRIPT_PATH} --host ${REMOTE_HOST}
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/${USER_ID}
Environment=HOME=${HOME}

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable voice-input.service
systemctl --user start voice-input.service

# Enable lingering so service starts on boot even without login
loginctl enable-linger $USER

echo ""
echo "Service installed and started!"
echo "Check status: systemctl --user status voice-input.service"
echo "View logs:    journalctl --user -u voice-input.service -f"
