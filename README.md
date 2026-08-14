# PersonalClipboard

Local Windows dictation overlay: microphone → CUDA Faster-Whisper → Ollama on `127.0.0.1` → clipboard. Speak or type a sentence, finish it, then paste with Ctrl+V. Audio, transcripts, and clipboard text stay on this PC.

Hardware target: **Intel i9-14900K** + **NVIDIA RTX 4070 Ti SUPER** (16 GB).

![PersonalClipboard overlay](docs/images/overlay.png)

The HUD is a translucent always-on-top tool window. **Mic** is the privacy kill switch. **Voice** shows the live partial and the last sentence that landed on the clipboard. **Type** is the same correct-and-copy flow from the keyboard. **Meeting → Record** transcribes the room to a markdown file on the desktop and does not write the clipboard.

## Easy install (Windows)

You need a recent **NVIDIA driver** (CUDA 12 capable), **Python 3.11 or 3.12**, and [Ollama for Windows](https://ollama.com/download). You do **not** need to install the CUDA Toolkit if `pip` can install the `nvidia-*-cu12` wheels listed in `pyproject.toml`.

```powershell
gh repo clone BazoukaJo/PersonalClipboard
cd PersonalClipboard

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .

ollama pull qwen2.5-coder:1.5b

pythonw -m personalclipboard
```

The first launch downloads Faster-Whisper `large-v3-turbo` into the Hugging Face cache and loads it on the GPU. Use `python -m personalclipboard` instead of `pythonw` if you want a console for errors.

Windows Settings → Privacy → Microphone → allow desktop apps. After Whisper is ready, **Mic** turns on. Uncheck it to stop the WASAPI stream and idle CUDA ASR.

Full CUDA / cuDNN notes: [docs/SETUP.md](docs/SETUP.md).

## Use

| Action | What happens |
|---|---|
| Speak, end with `.` `?` `!` | Corrected sentence → clipboard. Paste with Ctrl+V. |
| Type, then Enter or `.` `?` `!` | Same correct-and-copy path. |
| **Copy** | Puts the last finished sentence on the clipboard again. |
| Say **paste last** | Focuses the last other window and pastes. |
| Say **copy last** | Copies the selection from the last other window. |
| Say **correct last** or **Ctrl+Shift+A** | Rewrites the current clipboard (works with Mic off). |
| **Record** | Meeting notes on the desktop. Speech goes to the file, not the clipboard. Headset calls only hear this microphone. |
| **Hide** | Overlay to the tray. Right-click for Show, Stop, Restart, About. |

Correction model: `qwen2.5-coder:1.5b` at `http://127.0.0.1:11434`. Partials never go to Ollama.

## Dev

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m pytest tests -q
```

Regenerate the overlay image:

```powershell
python scripts\capture_overlay.py
```

## Docs

| File | What it is |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | Driver, venv, Whisper smoke test, Ollama |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Threads, VRAM, latency |
| [docs/PRD.md](docs/PRD.md) | Requirements (Blueprint mode is deferred) |
| `AGENTS.md` | Constraints for coding agents |

## License

Private local tool. Not for distribution of microphone data.
