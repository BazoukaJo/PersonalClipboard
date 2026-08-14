# PersonalClipboard — Product Requirements Document

**Status:** v0.1 live dictation overlay (Windows). Blueprint / T3D mode is deferred and is not in the HUD.  
**Platform:** Windows 10/11  
**Hardware target:** Intel Core i9-14900K, NVIDIA GeForce RTX 4070 Ti SUPER (16 GB)  
**Privacy:** fully local; no cloud services

## 1. Problem

Dictation and clipboard cleanup should be always available at the OS layer, with GPU-class latency, without sending microphone audio or clipboard text off-machine. Unreal stays on the same GPU; the overlay is dictation only (no Blueprint / T3D switch).

## 2. Product goals

| ID | Goal |
|---|---|
| G1 | Always-on speech-to-text onto the Windows clipboard while a master enable switch is ON |
| G2 | Local LLM correction of committed sentences (grammar, punctuation, logic) |
| G3 | Global hotkey `Ctrl+Shift+A` reformats existing clipboard text using the active mode |
| G4 | Transparent always-on-top overlay for partials, status, and the enable switch |
| G5 | *(Deferred.)* Blueprint Mode emits paste-ready Unreal T3D — not in the overlay |
| G6 | Reject multi-speaker / low-confidence audio instead of corrupting the clipboard |

Non-goals for v1: cloud fallback, multi-language UI, diarization of every speaker, writing `.uasset` files, VS Code Continue as a runtime dependency.

## 3. Users and modes

Single local user on this PC.

| Mode | When | Output |
|---|---|---|
| Ambient dictation | Enable ON; sentence committed | Corrected prose → clipboard |
| Clipboard reformat | `Ctrl+Shift+A` | Rewrite of current clipboard (capture may be OFF) |
| Meeting notes | Record in the overlay | Transcript → desktop markdown; no clipboard |
| Blueprint | *(Deferred.)* Blueprint Mode + hotkey | T3D graph snippet → clipboard |

## 4. Functional requirements

### 4.1 Capture and enable switch

- FR-C1: Master enable switch in the overlay (and tray). ON starts WASAPI capture + CUDA ASR. OFF stops the PortAudio stream and idles the ASR worker (privacy kill switch).
- FR-C2: While ON, capture is always-on (overlapping windows). VAD must not drop capture; it may only hint chunk boundaries and confidence.
- FR-C3: Default format 16 kHz mono PCM via PyAudio (WASAPI).

### 4.2 Transcription

- FR-A1: Faster-Whisper on CUDA, model `large-v3-turbo` (`turbo`), `compute_type="float16"`.
- FR-A2: Streaming via ~1.0 s windows and 200–300 ms hop; `condition_on_previous_text=False`.
- FR-A3: Partials update the overlay only. Committed sentences may be sent to Ollama.
- FR-A4: `beam_size=1` for partials, `beam_size=3` for commit.

### 4.3 Correction and clipboard

- FR-L1: Ollama Python client talks only to `http://127.0.0.1:*`.
- FR-L2: Default correction model: `qwen2.5-coder:1.5b` (VRAM headroom for Unreal).
- FR-L3: Skip or timeout an in-flight correction if a newer committed sentence is ready.
- FR-L4: Committed + corrected text is written with `QClipboard` (Qt).
- FR-L5: `Ctrl+Shift+A` is a **global** hotkey (`pynput`); Qt shortcuts are insufficient.

### 4.4 Overlay

- FR-U1: PyQt6 frameless, translucent, always-on-top tool window + system tray.
- FR-U2: Shows partial hypothesis, last commit, and status `listening | uncertain | locked | off`.
- FR-U3: Enable switch is visible and reachable without focusing another app.

### 4.5 Cacophony

- FR-N1: Gate commits on Whisper `no_speech_prob` and average logprob.
- FR-N2: On reject, do **not** overwrite the clipboard; overlay shows `uncertain`.
- FR-N3: Optional target-speaker lock (CPU embedding, enroll 5–10 s) is v1.1; not on the ASR hot path. No pyannote in v1.

### 4.6 Meeting notes

- FR-M1: Record transcribes the room to `Desktop/Meeting YYYY-MM-DD HHMM.md`.
- FR-M2: While recording, spoken commits do not write the clipboard. Copy is disabled.
- FR-M3: Do not write WAV. Headset / remote speakers are not captured without loopback (known gap).

### 4.7 Blueprint Mode (deferred)

- FR-B1–B3: Out of the overlay. T3D fixtures remain under `ue/` for a later pass. Do not add a Blueprint switch to the HUD.

## 5. Non-functional requirements

### 5.1 Privacy

- NFR-P1: Audio, transcripts, clipboard, and LLM requests never leave this PC.
- NFR-P2: No telemetry, analytics, or crash-report uploads.
- NFR-P3: Microphone audio is not written to disk by default. Debug WAV requires an explicit config flag and is gitignored.
- NFR-P4: Ollama must not be advertised on LAN interfaces.

### 5.2 Latency (enable ON)

| Stage | Budget |
|---|---|
| Capture + ring buffer | 20–50 ms |
| Window hop | 200–300 ms |
| Turbo FP16 decode (~1 s chunk) | 50–120 ms on 4070 Ti SUPER |
| Overlay partials | hop cadence; **target < 400 ms** end-to-end |
| Ollama correction (`qwen2.5-coder:1.5b`) | 20–80 ms **after commit** |
| Clipboard commit | **target < 1 s** after end of sentence |

### 5.3 Resources

- Whisper turbo FP16 resident ~3 GB. Correction LLM (`qwen2.5-coder:1.5b`) ~1 GB. Leave headroom on 16 GB for Unreal Editor.
- Audio callback must not allocate GPU, take Python locks, or touch Qt.

## 6. Technical stack (Windows)

| Layer | Library / tool |
|---|---|
| UI | PyQt6 |
| Capture | PyAudio (WASAPI) |
| ASR | faster-whisper (CTranslate2), CUDA 12 + cuDNN 9 |
| LLM | ollama (Python client), localhost |
| Hotkeys | pynput |
| Arrays | numpy |
| Language | Python 3.11 or 3.12 |

Optional later: `sounddevice` as a WASAPI fallback if PyAudio device enumeration fails.

## 7. Acceptance criteria (v1)

1. With enable OFF, no PortAudio stream is active and the overlay shows `off`.
2. With enable ON, spoken sentences appear as overlay partials in under ~400 ms on the target GPU and land on the clipboard (corrected) within ~1 s of sentence end in a quiet room.
3. Overlapping speech / low confidence does not replace a previous good clipboard value.
4. `Ctrl+Shift+A` rewrites clipboard text with capture OFF.
5. *(Deferred.)* Blueprint Mode clipboard content pastes as nodes in a stock UE5 Blueprint graph.
6. Packet capture / firewall: no outbound connections except localhost Ollama.

## 8. Out of scope (v0.1)

Cloud STT/LLM, telemetry, WAV persistence, WASAPI loopback for meeting playback, Blueprint / T3D in the overlay, Continue/VS Code as a runtime. See `docs/SETUP.md` for install.
