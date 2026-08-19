# PersonalClipboard — Architecture

Target machine: **i9-14900K** (audio I/O, Qt, LLM HTTP, optional speaker embedding on P-cores) and **RTX 4070 Ti SUPER 16 GB** (resident Faster-Whisper + Ollama weights).

Whisper is a fixed-context encoder-decoder. “Near-zero delay” is an engineering pattern: **resident CUDA weights**, **short overlapping windows**, and **no LLM on partials**.

## 1. Pipeline

```
Mic (WASAPI via PyAudio, sounddevice fallback)
  → callback (~20 ms, 16 kHz mono)
  → lock-free ring buffer
  → ASR worker (faster-whisper CUDA, overlapping windows)
       → partial hypothesis → Qt overlay
       → committed sentence → LLM worker (Ollama 127.0.0.1)
            → QClipboard
Type field (focused only) → debounce → LLM worker complete → grey ghost; Tab inserts
Quiet (app VAD, Mic ON) → stop stream + idle CUDA; short probe wakes on speech
Enable switch OFF → stop stream, stop probe, idle ASR (no wake)
Ctrl+Shift+A → LLM worker (Type human or AI prompt) → QClipboard
Ctrl+Shift+R → Type field; again → last other-app text field
Meeting Record → WASAPI loopback of speakers/headphones + mic ring → mix on ASR hop
```

## 2. Threads

| Thread | Core affinity (intent) | Allowed work | Forbidden |
|---|---|---|---|
| PortAudio callback | realtime | Copy PCM into ring buffer; return immediately | Locks, GPU, Qt, alloc-heavy Python |
| WASAPI loopback | meeting only | Copy speaker mix into a second ring | GPU, Qt, PortAudio callback |
| ASR worker | P-core + CUDA | Window slice, mix meeting rings, Faster-Whisper, confidence gates | Qt widgets, Ollama HTTP |
| LLM worker | P-core (HTTP) | Localhost generate; timeout/skip stale jobs | Audio callback, CUDA Whisper, Qt widgets |
| Qt main | UI | Overlay, tray, enable switch, clipboard write | Whisper, Ollama, blocking I/O |

Use `queue.Queue` or equivalent between ASR → Qt (partials/commits) and ASR → LLM (commits only). Clipboard writes happen on the Qt thread via signals/slots.

## 3. Streaming ASR pattern

Faster-Whisper has no native partial decoder. v1 uses chunk-and-stitch:

- Ring buffer holds several seconds of PCM (16 s so record hops can fall behind).
- Dictation: every **200–300 ms**, transcribe the last **~2.0 s**.
- Meeting/Playback: every **~800 ms**, transcribe the last **~6.0 s**, `beam_size=3`. WASAPI loopback prefers the console (multimedia) device so YouTube plays into the same mix.
- `condition_on_previous_text=False` to limit hallucination drift across windows.
- Partials: `beam_size=1`. Commit (punctuation or pause / stable tail): `beam_size=3`.
- Stitch by preferring the stable prefix of consecutive windows; emit a commit when the tail stays unchanged across hops or a pause is detected.

```python
# Load once on the ASR worker — never from the audio callback or Qt thread
from faster_whisper import WhisperModel

model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
segments, info = model.transcribe(
    audio_window,
    language=None,
    task="transcribe",
    multilingual=True,  # EN/FR/ZH (and mixed) per segment; do not translate
    beam_size=1,
    condition_on_previous_text=False,
    vad_filter=False,  # Whisper Silero filter off; app QuietIdle owns idle/wake
)
```

Keep Faster-Whisper `vad_filter=False` so the app owns chunking. App-level VAD (`QuietIdle`) may **stop the streaming callback** after `vad_silence_ms` of quiet and idle CUDA; `WakeProbe` peeks (~80 ms) until speech, then capture resumes. That is not Whisper's `vad_filter`. Meeting Record does not VAD-idle. Mic OFF still stops the probe.

## 4. Latency budget

End-to-end overlay partial ≈ hop + decode (not a 30 s Whisper chunk).

| Stage | Budget (ms) | Notes |
|---|---|---|
| Capture + buffer | 20–50 | 20 ms frames |
| Window hop | 200–300 | Dominates “near-zero” |
| Turbo FP16 decode | 50–120 | ~1 s audio on 4070 Ti SUPER |
| Overlay update | hop cadence | Target **< 400 ms** partials |
| Ollama `qwen2.5:1.5b` | 20–80 | After commit only |
| Clipboard commit | — | Target **< 1 s** after sentence end |

If hop + decode exceeds 400 ms, shrink hop before shrinking the model. If another GPU app is heavy, keep Whisper loaded and consider CPU offload for Ollama rather than unloading ASR.

## 5. VRAM split (16 GB)

| Resident | Approx. VRAM | Role |
|---|---|---|
| faster-whisper `large-v3-turbo` FP16 | ~3 GB | Resident ASR while Mic is ON (idled during VAD quiet) |
| `qwen2.5:1.5b` (Ollama) | ~1 GB | Sentence correction |
| Other GPU apps + OS | remainder | Must still fit |
| Headroom | ~7+ GB | Keep the 1.5B default while the card is shared |

Do not default a 7B+ correction model while other GPU apps may be open.

## 6. Enable switch and VAD idle

**Mic OFF** is a hard privacy boundary:

1. Stop the streaming capture (PyAudio or sounddevice; callback no longer runs).
2. Stop `WakeProbe` (no background peeks).
3. ASR worker waits on an idle event (no further CUDA transcribe).
4. Overlay status `off`. LLM worker remains available for `Ctrl+Shift+A`.

**Mic ON** starts the stream and hop loop. After `vad_silence_ms` of VoiceGate silence (default 1.5 s, HUD toggle), the app stops the stream, idles CUDA, overlay status `quiet`, and `WakeProbe` takes short blocking peeks until speech. Whisper weights stay in VRAM. Meeting Record keeps the stream up.

## 7. Cacophony (v1)

No pyannote on the hot path.

1. Drop commits with high `no_speech_prob` or poor average logprob.
2. Never clobber clipboard on reject; overlay `uncertain`.
3. v1.1: optional target-speaker embedding on CPU (5–10 s enrollment); cosine gate. Overlay `locked` when the gate is active and passing.

## 8. Clipboard and hotkey

- Ambient: commit → (optional) Ollama → `QClipboard.setText`.
- Type field: while focused, debounce → same Ollama model as a **continuation** (not a rewrite). Grey ghost; Tab inserts. Escape clears. Never on ASR partials or Meeting Record.
- `Ctrl+Shift+A`: read clipboard → Ollama with the Type-row prompt (human grammar fix, or AI reformulation) → write back. Independent of enable. Spoken dictation always uses the human prompt.
- `Ctrl+Shift+R`: focus the Type field. If it already has focus, restore the last foreign window's focused control (Explorer included). Poll records `GetForegroundWindow` + `GetGUIThreadInfo` hwndFocus while the overlay is not foreground.
- Register hotkeys with `pynput` (global). `QShortcut` only works when the overlay is focused.
- One process only. A new launch asks the running instance to quit (CUDA unload), then binds the instance socket. If the old process hangs, it is terminated.

## 9. Meeting notes

Meeting Record uses the same ASR worker with VoiceGate lock off and voice commands off. While recording, a WASAPI loopback stream copies the default playback mix (console/multimedia endpoint first, then communications) into a second ring. Meeting mixes that ring with the microphone window. Playback Record uses the loopback ring only (YouTube and other app audio; no microphone). Overlay **Records** lists desktop `Meeting *.md` and `Playback *.md` files; opening a row shows the full note. Commits are stitched overlapping windows, then localhost-corrected, then appended. Audio is not written to disk. The overlay Copy control is disabled while recording. Dictation stays microphone-only; loopback stops when Record stops. Mic OFF stops a meeting; playback can continue with the microphone off.

## 10. Module map

| Module | Responsibility |
|---|---|
| `app.py` | `QApplication`, tray, start/stop workers |
| `config.py` | Models, hop, hotkey, Ollama host, HUD language/opacity/VAD/predict/geometry (LOCALAPPDATA) |
| `audio/capture.py` | PyAudio WASAPI → ring; `sounddevice` fallback; meeting loopback ring |
| `audio/loopback.py` | WASAPI render-mix capture (headphones/speakers), meeting only |
| `audio/mix.py` | Mix mic + loopback windows on the ASR thread |
| `audio/probe.py` | Short peeks to wake capture after VAD idle |
| `asr/engine.py` | CUDA Faster-Whisper worker |
| `asr/vad.py` | Silence timer (`QuietIdle`) |
| `llm/corrector.py` | Localhost Ollama + `/api/tags` + Type continuation |
| `llm/complete.py` | Ghost suffix gating (Type field only) |
| `clipboard/service.py` | Qt clipboard read/write |
| `ui/overlay.py` | Translucent HUD + status |
| `ui/predict_edit.py` | Type field ghost + Tab accept |
| `ui/settings_panel.py` | Modal language, opacity, models, VAD, type-ahead |
| `ui/i18n.py` | en / fr / es / de HUD strings |
| `hotkeys/bindings.py` | `Ctrl+Shift+A`, `Ctrl+Shift+R` |
| `modes/ambient.py` | Human prose correction and AI reformulation prompts |
| `modes/complete.py` | Type-ahead continuation prompt |
| `notes/meeting.py` | Desktop markdown meeting/playback notes |
| `notes/library.py` | Index desktop transcripts for the Records modal |
| `ui/records_dialog.py` | Records library + full-note view |
| `ui/win11_resize.py` | Frameless Win11 resize hit-test |
| `ui/tray.py` | Tray, About, restart (prefers `dist/.../PersonalClipboard.exe`) |

## 11. Failure modes

| Failure | Behavior |
|---|---|
| CUDA unavailable | Refuse ASR start; overlay error; clipboard hotkey may still use Ollama CPU |
| Ollama down | Pass through raw Whisper commit (corrector fail-open; overlay still reports Copied — known gap) |
| Stale LLM job | Drop result if a newer commit id exists |
| Device unplugged | Stop stream; overlay error; enable stays ON until user toggles or retry succeeds |
