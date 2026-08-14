# PersonalClipboard — Agent Brief

Local, always-on Windows desktop app: microphone → CUDA Faster-Whisper → localhost Ollama correction → clipboard, with a translucent PyQt6 overlay.

**Hardware target:** Intel i9-14900K + NVIDIA RTX 4070 Ti SUPER (16 GB).
**Phase:** live dictation overlay.

## Goals

- Near-real-time dictation onto the Windows clipboard while a **master enable switch** is ON.
- `Ctrl+Shift+A` reformats whatever is already on the clipboard (works with capture OFF).
- Meeting Record writes a desktop markdown file and does **not** copy to the clipboard.
- All audio, transcripts, and LLM traffic stay on this machine.

## Capture semantics

- Enable **ON**: always-on streaming Whisper (overlapping windows). Mic callback + CUDA ASR loop run continuously.
- Enable **OFF**: stop WASAPI capture and idle/stop the GPU ASR worker. This is the privacy kill switch.
- v1 does **not** VAD-gate capture. Silero/VAD may hint chunk boundaries and cacophony confidence only.

## Architecture (do not violate)

```
WASAPI mic → PyAudio callback → lock-free ring buffer
  → faster-whisper CUDA (large-v3-turbo, float16)
  → overlay partials
  → committed sentence → Ollama 127.0.0.1 → clipboard
Ctrl+Shift+A → Ollama (dictation prompt) → clipboard
Meeting Record → same ASR → desktop markdown (no clipboard)
```

- Audio callback: copy samples only. No locks, no GPU, no Qt.
- Qt main thread: overlay, tray, enable switch, `QClipboard` writes.
- ASR worker: CUDA. LLM worker: HTTP to localhost Ollama.
- **Never** send partial hypotheses to Ollama. Correct on commit or hotkey only.
- `condition_on_previous_text=False` on streaming windows.

Defaults: Whisper `large-v3-turbo` / `turbo`, `device="cuda"`, `compute_type="float16"`, `beam_size=1` partials / `3` commit. Correction model: `qwen2.5-coder:1.5b` (~1 GB) so other GPU apps can share VRAM. Do not default to 14B+.

Latency targets: overlay partials **< ~400 ms**; clipboard commit **< ~1 s** after end of sentence.

## Privacy

- No cloud STT/LLM, no telemetry, no crash-report uploads.
- Ollama must bind `127.0.0.1`.
- No audio persistence by default. Debug WAV only behind an explicit flag; never commit recordings.
- Clipboard contents never leave the machine.

## Modes

| Mode | Trigger | Output |
|---|---|---|
| Dictation | Mic ON, sentence ending in `.` `?` `!` | Corrected prose → clipboard |
| Type | Enter or `.` `?` `!` in the Type field | Same as dictation |
| Reformat | `Ctrl+Shift+A` or say correct last | Rewrite of current clipboard |
| Meeting | Record | Transcript → `Desktop/Meeting YYYY-MM-DD HHMM.md` |

## Package layout

```
src/personalclipboard/   app, config, audio, asr, llm, clipboard, ui, hotkeys, modes, notes
  hotkeys/bindings.py    global Ctrl+Shift+A (not global.py — keyword)
docs/                    PRD, ARCHITECTURE, SETUP, images/overlay.png
scripts/capture_overlay.py
tests/                   unit tests; no GPU required for stubs
```

## Do / don't

- **Do** keep public APIs typed; keep the overlay non-blocking.
- **Do** reject low-confidence / overlapping speech instead of clobbering the clipboard.
- **Don't** add network calls except `http://127.0.0.1:*` (Ollama).
- **Don't** put Faster-Whisper or Ollama work on the Qt thread or the PortAudio callback.
- **Don't** treat Continue/VS Code as required; Cursor is the coding agent. Ollama in this repo is the **in-app** corrector.

Full design: `docs/ARCHITECTURE.md`. Requirements: `docs/PRD.md`. Install: `docs/SETUP.md`.
