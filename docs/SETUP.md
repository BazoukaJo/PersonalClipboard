# PersonalClipboard — Install

Windows 10/11, Python **3.11 or 3.12**, NVIDIA driver that can run **CUDA 12**. The app installs CUDA 12 + cuDNN 9 **wheels** (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`, …). A full CUDA Toolkit install is optional.

This machine may already have CUDA Toolkit **13** (`cublas64_13.dll`). CTranslate2 still needs **CUDA 12** DLLs (`cublas64_12.dll`). The app prepends the wheel `bin` dirs to `PATH` before loading Whisper. Do not rename CUDA 13 DLLs to `_12`.

## 1. Prerequisites

1. NVIDIA Game Ready or Studio driver current enough for CUDA 12.
2. Python 3.11+ from python.org (check “Add python.exe to PATH”) or `py -3.11`.
3. [Ollama for Windows](https://ollama.com/download). It must listen on localhost only.
4. Windows Settings → Privacy → Microphone → allow desktop apps.

```powershell
nvidia-smi
py -3.11 --version
ollama --version
```

If `ctranslate2` errors on CUDA 12 + cuDNN 8, the cu12 wheels in `pyproject.toml` are the fix. Pin `ctranslate2==4.4.0` only if a newer wheel still looks for the wrong cuDNN.

## 2. Clone and venv

The GitHub repo is **private**. Use `gh` (you must be able to read `BazoukaJo/PersonalClipboard`):

```powershell
gh repo clone BazoukaJo/PersonalClipboard
cd PersonalClipboard
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

`pyproject.toml` installs: `faster-whisper`, `PyAudio`, `PyQt6`, `ollama`, `numpy`, `pynput`, and the NVIDIA CUDA 12 wheels.

PyAudio on Windows usually has a wheel on PyPI. If `pip` tries to compile it, install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).

## 3. CUDA Faster-Whisper smoke test

```powershell
python -c "from personalclipboard.asr.cuda_runtime import configure_cuda12_dlls; configure_cuda12_dlls(); from faster_whisper import WhisperModel; m = WhisperModel('large-v3-turbo', device='cuda', compute_type='float16'); print('cuda ok')"
```

First run downloads the CTranslate2 model into the Hugging Face cache. Expect ~3 GB VRAM in `nvidia-smi` while the process lives.

## 4. Ollama corrector

Ollama here is the **desktop app’s** sentence corrector, not the Cursor coding agent.

```powershell
ollama pull qwen2.5-coder:1.5b
ollama run qwen2.5-coder:1.5b "Reply with the single word: pong"
```

Keep the default at `qwen2.5-coder:1.5b` (~1 GB) while Unreal may share the 16 GB card. Do not bind Ollama to `0.0.0.0`.

## 5. Run

```powershell
pythonw -m personalclipboard
```

Use `python -m personalclipboard` for a console. After Whisper loads, Mic turns on. Uncheck Mic to idle capture and CUDA ASR. Ctrl+Shift+A still reformats the clipboard.

Preferred WASAPI input: a device whose name contains `maono` when present (`config.py` `preferred_input`).

## 6. Ready when

- [ ] `nvidia-smi` sees the GPU
- [ ] `.venv` has `faster-whisper` and `PyQt6`
- [ ] WhisperModel loads on `cuda` / `float16`
- [ ] `ollama run qwen2.5-coder:1.5b` works on `127.0.0.1`
- [ ] Overlay appears; tray icon has Show / Stop / Restart / About
- [ ] No cloud API keys in the repo
