# PersonalClipboard — Architecture

Target machine: **i9-14900K** (audio I/O, Qt, LLM HTTP, optional speaker embedding on P-cores) and **RTX 4070 Ti SUPER 16 GB** (resident Faster-Whisper + Ollama weights).

Whisper is a fixed-context encoder-decoder. “Near-zero delay” is an engineering pattern: **resident CUDA weights**, **short overlapping windows**, and **no LLM on partials**.

## 1. Pipeline

```
Mic (WASAPI)
  → PyAudio callback (~20 ms, 16 kHz mono)
  → lock-free ring buffer
  → ASR worker (faster-whisper CUDA, overlapping windows)
       → partial hypothesis → Qt overlay
       → committed sentence → LLM worker (Ollama 127.0.0.1)
            → QClipboard
Ctrl+Shift+A → LLM worker (active mode prompt) → QClipboard
Enable switch OFF → stop stream + idle ASR worker
```

## 2. Threads

| Thread | Core affinity (intent) | Allowed work | Forbidden |
|---|---|---|---|
| PortAudio callback | realtime | Copy PCM into ring buffer; return immediately | Locks, GPU, Qt, alloc-heavy Python |
| ASR worker | P-core + CUDA | Window slice, Faster-Whisper, confidence gates | Qt widgets, Ollama HTTP |
| LLM worker | P-core (HTTP) | Localhost generate; timeout/skip stale jobs | Audio callback, CUDA Whisper |
| Qt main | UI | Overlay, tray, enable switch, clipboard write | Whisper, Ollama, blocking I/O |

Use `queue.Queue` or equivalent between ASR → Qt (partials/commits) and ASR → LLM (commits only). Clipboard writes happen on the Qt thread via signals/slots.

## 3. Streaming ASR pattern

Faster-Whisper has no native partial decoder. v1 uses chunk-and-stitch:

- Ring buffer holds several seconds of PCM.
- Every **200–300 ms**, transcribe the last **~1.0 s**.
- `condition_on_previous_text=False` to limit hallucination drift across windows.
- Partials: `beam_size=1`. Commit (punctuation or pause / stable tail): `beam_size=3`.
- Stitch by preferring the stable prefix of consecutive windows; emit a commit when the tail stays unchanged across hops or a pause is detected.

```python
# Load once on the ASR worker — never from the audio callback or Qt thread
from faster_whisper import WhisperModel

model = WhisperModel("large-v3-turbo", device="cuda", compute_type="float16")
segments, info = model.transcribe(
    audio_window,
    beam_size=1,
    condition_on_previous_text=False,
    vad_filter=False,  # capture stays always-on while enable is ON
)
```

`vad_filter` stays off for capture policy. If Silero is added later, use it only as a **boundary/confidence hint**, not to skip the callback.

## 4. Latency budget

End-to-end overlay partial ≈ hop + decode (not a 30 s Whisper chunk).

| Stage | Budget (ms) | Notes |
|---|---|---|
| Capture + buffer | 20–50 | 20 ms frames |
| Window hop | 200–300 | Dominates “near-zero” |
| Turbo FP16 decode | 50–120 | ~1 s audio on 4070 Ti SUPER |
| Overlay update | hop cadence | Target **< 400 ms** partials |
| Ollama `qwen2.5-coder:1.5b` | 20–80 | After commit only |
| Clipboard commit | — | Target **< 1 s** after sentence end |

If hop + decode exceeds 400 ms, shrink hop before shrinking the model. If another GPU app is heavy, keep Whisper loaded and consider CPU offload for Ollama rather than unloading ASR.

## 5. VRAM split (16 GB)

| Resident | Approx. VRAM | Role |
|---|---|---|
| faster-whisper `large-v3-turbo` FP16 | ~3 GB | Always-on ASR while enable is ON |
| `qwen2.5-coder:1.5b` (Ollama) | ~1 GB | Sentence correction |
| Other GPU apps + OS | remainder | Must still fit |
| Headroom | ~7+ GB | Keep the 1.5B default while the card is shared |

Do not default a 7B+ correction model while other GPU apps may be open.

## 6. Enable switch

OFF is a hard privacy boundary:

1. Stop the PyAudio/WASAPI stream (callback no longer runs).
2. ASR worker exits its loop or waits on an idle event (no further CUDA transcribe).
3. Overlay status `off`. LLM worker remains available for `Ctrl+Shift+A`.

ON reverses 1–3 and keeps the Whisper model in VRAM (load once at app start or on first ON).

## 7. Cacophony (v1)

No pyannote on the hot path.

1. Drop commits with high `no_speech_prob` or poor average logprob.
2. Never clobber clipboard on reject; overlay `uncertain`.
3. v1.1: optional target-speaker embedding on CPU (5–10 s enrollment); cosine gate. Overlay `locked` when the gate is active and passing.

## 8. Clipboard and hotkey

- Ambient: commit → (optional) Ollama → `QClipboard.setText`.
- `Ctrl+Shift+A`: read clipboard → Ollama with the dictation system prompt → write back. Independent of enable.
- Register the hotkey with `pynput` (global). `QShortcut` only works when the overlay is focused.

## 9. Meeting notes

Meeting Record uses the same ASR worker with VoiceGate lock off and voice commands off. Commits append to a desktop markdown file. The overlay Copy control is disabled while recording.

## 10. Module map

| Module | Responsibility |
|---|---|
| `app.py` | `QApplication`, tray, start/stop workers |
| `config.py` | Enable flag, model names, hop, hotkey, Ollama host |
| `audio/capture.py` | PyAudio WASAPI → ring buffer |
| `asr/engine.py` | CUDA Faster-Whisper worker |
| `llm/corrector.py` | Localhost Ollama |
| `clipboard/service.py` | Qt clipboard read/write |
| `ui/overlay.py` | Transparent widget + status |
| `hotkeys/bindings.py` | `Ctrl+Shift+A` |
| `modes/ambient.py` | Prose correction prompt |
| `notes/meeting.py` | Desktop markdown meeting notes |
| `ui/win11_resize.py` | Frameless Win11 resize hit-test |

## 11. Failure modes

| Failure | Behavior |
|---|---|
| CUDA unavailable | Refuse ASR start; overlay error; clipboard hotkey may still use Ollama CPU |
| Ollama down | Pass through raw Whisper commit (corrector fail-open; overlay still reports Copied — known gap) |
| Stale LLM job | Drop result if a newer commit id exists |
| Device unplugged | Stop stream; overlay error; enable stays ON until user toggles or retry succeeds |
