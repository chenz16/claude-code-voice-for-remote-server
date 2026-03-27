# Claude Code Voice Input — Chinese Speech Recognition

按住 Right Alt 说中文，松开后自动识别并输入。使用阿里 [SenseVoiceSmall](https://github.com/FunAudioLLM/SenseVoice) 模型，中文识别精度优于 Whisper。

---

## Use Cases

### Use Case 1: Linux → Remote Server (SSH + tmux)

```
┌─────────────────────┐          SSH           ┌─────────────────────┐
│   Linux Host 本机     │ ───────────────────── │   Remote GPU Server  │
│                       │                       │                      │
│  🎤 麦克风             │                       │  tmux session        │
│  ↓                    │                       │    ↑                 │
│  arecord 录音          │                       │    │                 │
│  ↓                    │                       │    │                 │
│  SenseVoice 语音转文字  │  ── send-keys ──────> │  Claude Code 输入框  │
│                       │                       │                      │
│  按住 Right Alt 说话    │                       │  文字出现，手动回车确认 │
└─────────────────────┘                         └─────────────────────┘
```

**场景**：你在 Linux 桌面/笔记本上工作，Claude Code 跑在远程 GPU 服务器的 tmux 中。
语音在本机录制和识别，识别结果通过 SSH 发送到远程 tmux session。

**脚本**：`voice_input.py`

```bash
python3 voice_input.py --host user@remote-server-ip
```

### Use Case 2: Windows → 本地窗口（Claude Code / 任意应用）

```
┌──────────────────────────────────────────┐
│              Windows 11                    │
│                                            │
│  🎤 麦克风                                  │
│  ↓                                         │
│  sounddevice 录音                           │
│  ↓                                         │
│  SenseVoice 语音转文字                       │
│  ↓                                         │
│  Ctrl+V 粘贴到当前焦点窗口                    │
│                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │Claude Code│  │  浏览器   │  │  编辑器   │ │
│  └──────────┘  └──────────┘  └──────────┘ │
│                                            │
│  按住 Right Alt 说话，松开后文字粘贴到焦点窗口  │
└──────────────────────────────────────────┘
```

**场景**：你在 Windows 上直接使用 Claude Code（或任何其他应用）。
语音在本机录制和识别，识别结果自动粘贴到当前焦点窗口。

**脚本**：`voice_input_win.py`

```powershell
python voice_input_win.py
```

---

## 安装

### Use Case 1: Linux → Remote Server

```bash
# 系统依赖
sudo apt install alsa-utils

# Python 依赖
pip install funasr modelscope torch torchaudio evdev

# 加入 input 组（evdev 全局键盘监听需要）
sudo usermod -aG input $USER
# 重新登录生效

# SSH 密钥登录（免密码）
ssh-copy-id user@remote-server-ip

# 运行
python3 voice_input.py --host user@remote-server-ip
```

#### 可选：设为 systemd 开机自启

编辑 `setup_service.sh` 中的路径和主机地址，然后：

```bash
bash setup_service.sh
```

管理服务：

```bash
systemctl --user status voice-input.service     # 状态
journalctl --user -u voice-input.service -f      # 日志
systemctl --user restart voice-input.service     # 重启
systemctl --user stop voice-input.service        # 停止
```

### Use Case 2: Windows 本地

```powershell
# 安装 Python 3.11+（如未安装）
winget install Python.Python.3.11

# 安装依赖
pip install -r requirements_win.txt

# 运行
python voice_input_win.py
```

**注意**：如果 `python` 命令提示从 Microsoft Store 安装，需要关闭 App execution aliases：
Settings > Apps > Advanced app settings > App execution aliases → 关掉 python.exe 和 python3.exe

---

## 使用方法

1. 运行对应脚本（首次会下载 ~1GB 模型）
2. **切换到目标窗口**（Claude Code、终端、编辑器等）
3. **按住 Right Alt** 说中文
4. **松开** → 自动识别并输入
5. **Esc** 或 **Ctrl+C** 退出

---

## 文件说明

```
voice_input.py           # Linux 版 — SSH 远程 tmux 发送
voice_input_win.py       # Windows 版 — 本地剪贴板粘贴
voice_input_linux.py     # Linux / WSL 版 — 本地粘贴 + 远程模式可选
setup_service.sh         # Linux systemd 服务安装脚本
requirements_win.txt     # Windows Python 依赖
requirements_linux.txt   # Linux Python 依赖
setup.bat                # Windows 一键安装依赖
```

---

## 语音模型

使用阿里巴巴 [SenseVoiceSmall](https://github.com/FunAudioLLM/SenseVoice)：
- 中文（普通话 + 粤语）识别精度领先
- 支持英语、日语、韩语
- 含逆文本正则化（语音中的数字自动转为阿拉伯数字）
- 模型大小 ~1GB，本地运行，无需联网 API

## License

MIT
