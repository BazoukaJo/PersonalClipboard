"""QApplication lifecycle, tray, and worker start/stop."""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime

from PyQt6.QtCore import QObject, QRect, Qt, QTimer
from PyQt6.QtGui import QAction, QScreen
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from personalclipboard.asr.engine import AsrEngine
from personalclipboard.audio.capture import AudioCapture
from personalclipboard.audio.probe import WakeProbe
from personalclipboard.clipboard.history import ClipboardHistory
from personalclipboard.clipboard.service import ClipboardService
from personalclipboard.config import (
    OPACITY_MAX,
    OPACITY_MIN,
    Settings,
    history_path,
    load_settings,
    save_settings,
    saved_overlay_rect,
)
from personalclipboard.hotkeys.bindings import GlobalHotkeys
from personalclipboard.llm.corrector import Corrector
from personalclipboard.llm.variants import PhraseBank
from personalclipboard.llm.worker import LlmWorker
from personalclipboard.notes.meeting import MeetingNotes, desktop_directory
from personalclipboard.ui.bridge import UiBridge
from personalclipboard.ui.copy_cue import play_copy_cue
from personalclipboard.ui.history_dialog import HistoryDialog
from personalclipboard.ui.overlay import Overlay
from personalclipboard.ui.records_dialog import RecordsDialog
from personalclipboard.ui.tray import make_tray_icon, show_about, spawn_new_instance
from personalclipboard.windows.input import WindowInput


def _queue(signal: object, slot: object, queued: Qt.ConnectionType) -> None:
    """QueuedConnection: worker emits must not run Qt slots on the worker thread."""
    getattr(signal, "connect")(slot, queued)


def _visible_on_screens(qt: QApplication, x: int, y: int, width: int, height: int) -> bool:
    rect = QRect(x, y, width, height)
    return any(screen.availableGeometry().intersects(rect) for screen in qt.screens())


class PersonalClipboardApp(QObject):
    """Must be a QObject so worker-thread signals queue onto the Qt thread."""

    def __init__(
        self,
        qt: QApplication,
        settings: Settings,
        *,
        start_background: bool = True,
        history: ClipboardHistory | None = None,
    ) -> None:
        super().__init__(qt)
        self._booting = True
        self._settings = settings
        self._bridge = UiBridge(self)
        self._capture = AudioCapture(settings)
        self._asr = AsrEngine(
            settings,
            self._capture.ring,
            on_partial=self._bridge.partial.emit,
            on_commit=self._bridge.commit.emit,
            on_status=self._bridge.status.emit,
            on_error=self._bridge.error.emit,
            on_command=self._bridge.command.emit,
            on_vad_idle=self._bridge.vad_idle.emit,
        )
        self._asr.set_loop_ring(self._capture.loop_ring)
        self._corrector = Corrector(settings)
        self._llm = LlmWorker(
            self._corrector,
            self._emit_corrected,
            self._emit_predicted,
            self._emit_record_corrected,
        )
        self._overlay = Overlay()
        clipboard = qt.clipboard()
        if clipboard is None:
            raise RuntimeError("Qt clipboard is unavailable")
        self._history = history or ClipboardHistory(history_path())
        self._clipboard = ClipboardService(clipboard, self._history)
        self._hotkeys = GlobalHotkeys(
            settings,
            self._bridge.reformat_requested.emit,
            self._bridge.type_focus_requested.emit,
        )
        self._windows = WindowInput()
        self._last_ready = ""
        self._commit_source = "audio"
        self._typed_original = ""
        self._phrases = PhraseBank()
        self._stopped = False
        self._meeting: MeetingNotes | None = None
        self._meeting_owned_capture = False
        self._record_kind = ""
        self._record_owned_asr = False
        self._vad_sleeping = False
        self._want_mic = False
        self._start_mic_on_ready = True
        self._probe = WakeProbe(settings, self._bridge.vad_wake.emit)
        self._qt = qt
        self._tray: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._focus_timer = QTimer(qt)
        self._focus_timer.setInterval(200)
        self._focus_timer.timeout.connect(self._windows.poll)
        self._focus_timer.start()
        self._persist_timer = QTimer(self)
        self._persist_timer.setSingleShot(True)
        self._persist_timer.setInterval(400)
        self._persist_timer.timeout.connect(self._persist_settings)
        self._prepare_overlay(qt)
        self._fill_settings([])
        self._booting = False
        if start_background:
            QTimer.singleShot(0, self._start_workers)

    def _prepare_overlay(self, qt: QApplication) -> None:
        self._overlay.apply_language(self._settings.ui_language)
        self._overlay.set_opacity(self._settings.overlay_opacity)
        self._overlay.set_predict_enabled(self._settings.predict_enabled)
        self._overlay.set_correction_mode(self._settings.correction_mode)
        self._connect_signals()
        self._overlay.set_listen_enabled(False)
        self._overlay.set_status("loading")
        self._overlay.set_message("Loading Whisper on CUDA…")
        self._place_overlay(qt)
        self._overlay.show()
        self._init_tray(qt)

    def _start_workers(self) -> None:
        threading.Thread(target=self._load_model, name="asr-load", daemon=True).start()
        threading.Thread(target=self._load_ollama_models, name="ollama-tags", daemon=True).start()
        try:
            self._hotkeys.start()
        except Exception as exc:
            self._overlay.set_message(f"Hotkey failed: {exc}")

    def _connect_signals(self) -> None:
        queued = Qt.ConnectionType.QueuedConnection
        _queue(self._bridge.partial, self._overlay.show_partial, queued)
        _queue(self._bridge.status, self._overlay.set_status, queued)
        _queue(self._bridge.commit, self._on_speech_commit, queued)
        _queue(self._bridge.corrected, self._on_corrected, queued)
        _queue(self._bridge.error, self._on_error, queued)
        _queue(self._bridge.model_ready, self._on_model_ready, queued)
        _queue(self._bridge.reformat_requested, self._on_reformat, queued)
        _queue(self._bridge.command, self._on_command, queued)
        _queue(self._bridge.vad_idle, self._enter_vad_idle, queued)
        _queue(self._bridge.vad_wake, self._leave_vad_idle, queued)
        _queue(self._bridge.ollama_models, self._fill_settings, queued)
        _queue(self._bridge.predicted, self._on_predicted, queued)
        _queue(self._bridge.type_focus_requested, self._on_type_focus, queued)
        _queue(self._bridge.record_corrected, self._on_record_corrected, queued)
        self._overlay.enable_toggled.connect(self._set_capture)
        self._overlay.hide_requested.connect(self._overlay.hide)
        self._overlay.copy_requested.connect(self._copy_ready)
        self._overlay.history_requested.connect(self._open_history)
        self._overlay.records_requested.connect(self._open_records)
        self._overlay.phrase_completed.connect(self._on_typed_commit)
        self._overlay.prediction_requested.connect(self._on_prediction_requested)
        self._overlay.meeting_toggled.connect(self._on_meeting_toggled)
        self._overlay.record_start_requested.connect(self._start_record)
        self._overlay.record_stop_requested.connect(self._on_record_stop)
        self._overlay.retry_requested.connect(self._on_retry_requested)
        self._overlay.correction_mode_changed.connect(self._on_correction_mode_changed)
        panel = self._overlay.settings
        panel.language_changed.connect(self._on_language_changed)
        panel.opacity_changed.connect(self._on_opacity_changed)
        panel.whisper_changed.connect(self._on_whisper_changed)
        panel.ollama_changed.connect(self._on_ollama_changed)
        panel.vad_changed.connect(self._on_vad_changed)
        panel.predict_changed.connect(self._on_predict_changed)
        self._overlay.geometry_changed.connect(self._schedule_persist)

    def _emit_corrected(self, _jid: int, text: str) -> None:
        self._bridge.corrected.emit(text)

    def _emit_predicted(self, prefix: str, suffix: str) -> None:
        self._bridge.predicted.emit(prefix, suffix)

    def _emit_record_corrected(self, text: str) -> None:
        self._bridge.record_corrected.emit(text)

    def _init_tray(self, qt: QApplication) -> None:
        icon = make_tray_icon()
        qt.setWindowIcon(icon)
        self._overlay.setWindowIcon(icon)
        self._tray = QSystemTrayIcon(icon, qt)
        self._tray.setToolTip("PersonalClipboard — right-click for Stop, Restart, About")
        menu = QMenu()
        show_act = QAction("Show overlay", menu)
        show_act.triggered.connect(self._show_overlay)
        stop_act = QAction("Stop", menu)
        stop_act.triggered.connect(qt.quit)
        restart_act = QAction("Restart", menu)
        restart_act.triggered.connect(self._restart)
        about_act = QAction("About", menu)
        about_act.triggered.connect(self._show_about)
        menu.addAction(show_act)
        menu.addSeparator()
        menu.addAction(stop_act)
        menu.addAction(restart_act)
        menu.addSeparator()
        menu.addAction(about_act)
        self._tray_menu = menu
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _show_about(self) -> None:
        show_about(self._overlay)

    def _restart(self) -> None:
        spawn_new_instance()
        self._qt.quit()

    def _show_overlay(self) -> None:
        self._overlay.show()
        self._overlay.raise_()

    def _on_type_focus(self) -> None:
        if self._overlay.type_field_active():
            if self._windows.focus_last_foreign():
                self._overlay.release_type_field()
                return
            self._overlay.set_message("Click another app's field, then Ctrl+Shift+R.")
            return
        self._show_overlay()
        hwnd = int(self._overlay.winId())
        self._windows.focus_hwnd(hwnd)
        self._overlay.focus_type_field()

    def _place_overlay(self, qt: QApplication) -> None:
        screen = qt.primaryScreen()
        if screen is None:
            return
        saved = saved_overlay_rect(self._settings)
        if saved is not None and _visible_on_screens(qt, *saved):
            self._overlay.setGeometry(*saved)
            self._overlay.clamp_to_screen()
        else:
            geo = screen.availableGeometry()
            hint = self._overlay.sizeHint()
            width = min(max(520, hint.width()), geo.width())
            height = min(max(hint.height(), self._overlay.minimumHeight()), geo.height())
            self._overlay.resize(width, height)
            x = geo.x() + (geo.width() - self._overlay.width()) // 2
            y = geo.y() + 24
            self._overlay.move(x, y)
        self._watch_screens(qt)

    def _watch_screens(self, qt: QApplication) -> None:
        qt.primaryScreenChanged.connect(lambda _screen: self._overlay.clamp_to_screen())
        qt.screenAdded.connect(self._bind_screen)
        for screen in qt.screens():
            self._bind_screen(screen)

    def _bind_screen(self, screen: QScreen | None) -> None:
        if screen is None:
            return
        screen.availableGeometryChanged.connect(self._overlay.clamp_to_screen)
        screen.logicalDotsPerInchChanged.connect(self._overlay.clamp_to_screen)

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_overlay()

    def _load_model(self) -> None:
        self._asr.load()
        self._bridge.model_ready.emit()

    def _on_model_ready(self) -> None:
        if self._asr.ready:
            self._overlay.set_listen_enabled(True)
            if self._start_mic_on_ready:
                self._overlay.set_enable_checked(True)
                self._set_capture(True)
            self._start_mic_on_ready = True
            return
        self._overlay.set_status("error")
        self._overlay.set_message(self._asr.load_error or "CUDA Whisper unavailable")
        self._overlay.set_listen_enabled(False)

    def _set_capture(self, enabled: bool) -> None:
        self._want_mic = enabled
        if not enabled:
            self._vad_sleeping = False
            self._probe.stop()
        if enabled:
            if not self._asr.ready:
                self._overlay.set_enable_checked(False)
                self._overlay.set_message("Waiting for Whisper to load…")
                return
            try:
                self._capture.start()
                if self._meeting is None:
                    self._asr.start()
            except Exception as exc:
                self._overlay.set_enable_checked(False)
                self._overlay.set_status("error")
                self._overlay.set_message(str(exc))
                self._capture.stop()
                return
            self._overlay.set_status("listening")
            mic = self._capture.device_name or "microphone"
            extra = " (sounddevice)" if self._capture.backend == "sounddevice" else ""
            self._overlay.set_message(
                f"Listening on {mic}{extra}. Finish with a period to copy."
            )
            return
        if self._meeting is not None and self._record_kind == "playback":
            self._capture.stop()
            self._overlay.set_status("recording")
            self._overlay.set_message("Mic off. Playback recording continues from speakers.")
            return
        if self._meeting is not None:
            self._stop_meeting(restore_mic=False)
        self._asr.stop()
        self._capture.stop_loopback()
        self._capture.stop()
        self._overlay.set_status("off")
        self._overlay.show_partial("")
        self._overlay.set_message("Mic off. Check Mic to listen.")

    def _on_speech_commit(self, text: str) -> None:
        if self._meeting is not None:
            self._llm.submit_record(text)
            self._overlay.set_message("Correcting…")
            return
        self._finish_phrase(text, "audio")

    def _on_typed_commit(self, text: str) -> None:
        self._finish_phrase(text, "typed")

    def _finish_phrase(self, text: str, source: str) -> None:
        if not any(char.isalnum() for char in text):
            return
        self._commit_source = source
        self._phrases.reset(text)
        if source == "typed":
            self._typed_original = text
            self._overlay.show_typed_phrase(text, state="correcting")
        else:
            self._overlay.show_audio_phrase(text, state="correcting")
        self._overlay.set_message("Correcting…")
        self._llm.submit(text, mode=self._correction_mode_for(source))

    def _on_corrected(self, text: str) -> None:
        if self._stopped or not text.strip():
            return
        shown = self._phrases.record(text)
        self._publish_phrase(shown, log=True)

    def _on_retry_requested(self) -> None:
        if self._stopped or self._meeting is not None:
            return
        if self._phrases.retrying:
            return
        nxt = self._phrases.step()
        if nxt is not None:
            self._publish_phrase(nxt, log=False)
            return
        original, temperature, seed = self._phrases.begin_retry()
        if not original:
            self._phrases.retrying = False
            return
        current = self._phrases.current()
        if self._commit_source == "typed":
            self._overlay.show_typed_phrase(current, state="correcting")
        else:
            self._overlay.show_audio_phrase(current, state="correcting")
        self._overlay.set_message("Correcting…")
        self._llm.submit(
            original,
            temperature=temperature,
            seed=seed,
            vary=True,
            mode=self._correction_mode_for(self._commit_source),
        )

    def _publish_phrase(self, text: str, *, log: bool) -> None:
        stripped = text.strip()
        if not stripped:
            return
        previous = self._last_ready
        self._last_ready = stripped
        self._clipboard.write(stripped, log=log)
        if self._commit_source == "typed":
            self._overlay.show_typed_phrase(stripped)
            self._overlay.apply_typed_correction(
                self._typed_original, stripped, previous=previous
            )
        else:
            self._overlay.show_audio_phrase(stripped)
        self._overlay.set_message("On clipboard. Press Ctrl+V to paste.")

    def _on_reformat(self) -> None:
        current = self._clipboard.read()
        if not current.strip():
            self._overlay.set_message("Clipboard is empty")
            return
        self._phrases.reset(current)
        self._overlay.set_message("Correcting clipboard…")
        self._commit_source = "typed"
        self._typed_original = current
        self._overlay.show_typed_phrase(current, state="correcting")
        self._llm.submit(current, mode=self._correction_mode_for("typed"))

    def _on_command(self, command: str) -> None:
        if command == "paste_last":
            self._paste_last()
        elif command == "copy_last":
            self._copy_last()
        elif command == "correct_last":
            self._on_reformat()

    def _copy_ready(self) -> None:
        text = self._last_ready or self._clipboard.read()
        if not text.strip():
            self._overlay.set_message("Nothing to copy yet.")
            return
        self._clipboard.write(text)
        self._overlay.set_message("On clipboard. Press Ctrl+V to paste.")

    def _paste_last(self) -> None:
        text = self._last_ready or self._clipboard.read()
        if not text.strip():
            self._overlay.set_message("Nothing to paste yet.")
            return
        self._clipboard.write(text)
        if not self._windows.focus_last_foreign():
            self._overlay.set_message("Click the target field, then say paste last.")
            return
        self._windows.paste()
        self._overlay.set_message("Pasted into the other window.")

    def _copy_last(self) -> None:
        if not self._windows.focus_last_foreign():
            self._overlay.set_message("Click another app, select text, then say copy last.")
            return
        self._windows.copy()
        qt = QApplication.instance()
        if qt is not None:
            qt.processEvents()
        time.sleep(0.12)
        if qt is not None:
            qt.processEvents()
        text = self._clipboard.read()
        if not text.strip():
            self._overlay.set_message("No selection copied. Select text, then say copy last.")
            return
        self._last_ready = text
        self._commit_source = "typed"
        self._typed_original = text
        self._phrases.reset(text)
        self._history.append(text)
        self._overlay.show_typed_phrase(text)
        self._overlay.set_typed(text)
        self._overlay.set_message("Copied selection from the other window.")
        play_copy_cue()

    def _on_error(self, message: str) -> None:
        self._overlay.set_message(message)

    def _on_record_corrected(self, text: str) -> None:
        notes = self._meeting
        if notes is None or self._stopped or not text.strip():
            return
        notes.append(text)
        self._overlay.show_meeting_notes(notes.preview())

    def _on_meeting_toggled(self, want: bool) -> None:
        if want:
            self._start_record("meeting")
            return
        self._stop_meeting()

    def _on_record_stop(self) -> None:
        self._stop_meeting()

    def _start_meeting(self) -> None:
        self._start_record("meeting")

    def _start_record(self, kind: str = "meeting") -> None:
        if self._meeting is not None:
            return
        kind = "playback" if kind == "playback" else "meeting"
        self._probe.stop()
        self._vad_sleeping = False
        if not self._asr.ready:
            self._overlay.set_message("Waiting for Whisper to load…")
            return
        owned_mic = False
        owned_asr = False
        if kind == "meeting" and not self._capture.active:
            try:
                self._capture.start()
                if not self._asr.running:
                    self._asr.start()
            except Exception as exc:
                self._overlay.set_message(str(exc))
                return
            owned_mic = True
            self._want_mic = True
            self._overlay.set_enable_checked(True)
        elif kind == "playback":
            try:
                if not self._asr.running:
                    self._asr.start()
                    owned_asr = not self._want_mic
            except Exception as exc:
                self._overlay.set_message(str(exc))
                return
        self._capture.ring.clear()
        self._capture.loop_ring.clear()
        loop_ok = self._capture.start_loopback()
        self._asr.set_record_mode(kind)
        if kind == "playback":
            source = self._capture.loopback_name or "speakers"
        else:
            source = self._capture.device_name or "microphone"
            if loop_ok and self._capture.loopback_name:
                source = f"{source} + {self._capture.loopback_name}"
        try:
            notes = MeetingNotes(desktop_directory(), datetime.now(), source, kind=kind)
        except OSError as exc:
            self._asr.set_record_mode("")
            self._capture.stop_loopback()
            if owned_mic:
                self._overlay.set_enable_checked(False)
                self._set_capture(False)
            elif owned_asr and not self._want_mic:
                self._asr.stop()
            self._overlay.set_message(f"Could not create notes file: {exc}")
            return
        self._meeting = notes
        self._record_kind = kind
        self._meeting_owned_capture = owned_mic
        self._record_owned_asr = owned_asr
        self._overlay.set_meeting_recording(True, notes.filename, kind=kind)
        self._overlay.set_status("recording")
        if kind == "playback" and not loop_ok:
            self._overlay.set_message(
                "Speaker capture unavailable. Playback needs headphones or speakers."
            )
            self._stop_meeting(restore_mic=False)
            return
        if kind == "playback":
            self._overlay.set_message(
                f"Recording speakers only ({source}). "
                f"Notes save to the desktop as {notes.filename}."
            )
            return
        if loop_ok:
            self._overlay.set_message(
                f"Recording microphone and speakers on {source}. "
                f"Notes save to the desktop as {notes.filename}."
            )
            return
        self._overlay.set_message(
            f"Recording microphone only on {source} "
            f"(speaker capture unavailable). Notes save as {notes.filename}."
        )

    def _stop_meeting(self, *, restore_mic: bool = True) -> None:
        notes = self._meeting
        self._meeting = None
        leftover = self._asr.flush_remainder()
        self._asr.set_record_mode("")
        self._capture.stop_loopback()
        saved = ""
        if notes is not None:
            if leftover:
                notes.append(leftover)
                self._overlay.show_meeting_notes(notes.preview())
            try:
                notes.close()
            except OSError:
                pass
            saved = notes.filename
            self._overlay.set_meeting_recording(False, notes.filename)
            self._overlay.set_message(f"Meeting notes saved as {notes.filename} on the desktop.")
        else:
            self._overlay.set_meeting_recording(False)
        owned = self._meeting_owned_capture
        owned_asr = self._record_owned_asr
        self._meeting_owned_capture = False
        self._record_owned_asr = False
        self._record_kind = ""
        if restore_mic and owned:
            self._overlay.set_enable_checked(False)
            self._set_capture(False)
            if saved:
                self._overlay.set_message(f"Meeting notes saved as {saved} on the desktop.")
            return
        if owned_asr and not self._want_mic:
            self._asr.stop()
            self._overlay.set_status("off")
            if saved:
                self._overlay.set_message(f"Meeting notes saved as {saved} on the desktop.")
            return
        if self._capture.active:
            self._overlay.set_status("listening")

    def _enter_vad_idle(self) -> None:
        if self._meeting is not None or not self._want_mic or self._vad_sleeping:
            return
        self._vad_sleeping = True
        self._asr.stop()
        self._capture.stop()
        self._capture.ring.clear()
        self._overlay.set_status("quiet")
        self._probe.start()

    def _leave_vad_idle(self) -> None:
        if not self._vad_sleeping:
            return
        self._vad_sleeping = False
        self._probe.stop()
        if self._want_mic and self._asr.ready:
            try:
                self._capture.ring.clear()
                self._capture.start()
                self._asr.start()
            except Exception as exc:
                self._overlay.set_enable_checked(False)
                self._overlay.set_status("error")
                self._overlay.set_message(str(exc))
                return
            self._overlay.set_status("listening")

    def _correction_mode_for(self, source: str) -> str:
        if source == "typed" and self._overlay.correction_mode() == "ai":
            return "ai"
        return "human"

    def _on_correction_mode_changed(self, mode: str) -> None:
        if self._booting:
            return
        kind = "ai" if mode == "ai" else "human"
        if kind == self._settings.correction_mode:
            return
        self._settings.correction_mode = kind
        self._persist_settings()

    def _schedule_persist(self) -> None:
        if self._booting or self._stopped:
            return
        self._persist_timer.start()

    def _store_overlay_geometry(self) -> None:
        box = self._overlay.compact_geometry()
        self._settings.overlay_x = box.x()
        self._settings.overlay_y = box.y()
        self._settings.overlay_w = box.width()
        self._settings.overlay_h = box.height()

    def _persist_settings(self) -> None:
        if self._stopped:
            return
        self._store_overlay_geometry()
        save_settings(self._settings)

    def _on_language_changed(self, lang: str) -> None:
        if self._booting:
            return
        self._settings.ui_language = lang
        self._persist_settings()

    def _open_history(self) -> None:
        dialog = HistoryDialog(
            self._history.entries(),
            self._settings.ui_language,
            self._overlay,
        )
        dialog.copy_requested.connect(self._copy_history_entry)
        dialog.exec()

    def _open_records(self) -> None:
        from personalclipboard.notes.library import list_records

        dialog = RecordsDialog(
            list_records(desktop_directory()),
            self._settings.ui_language,
            self._overlay,
        )
        dialog.exec()

    def _copy_history_entry(self, text: str) -> None:
        if not text.strip():
            return
        self._clipboard.write(text, log=False)
        self._last_ready = text

    def _on_opacity_changed(self, percent: int) -> None:
        if self._booting:
            return
        self._settings.overlay_opacity = max(OPACITY_MIN, min(OPACITY_MAX, percent))
        self._persist_settings()

    def _on_whisper_changed(self, name: str) -> None:
        if self._booting or name == self._settings.whisper_model:
            return
        self._settings.whisper_model = name
        self._persist_settings()
        resume = self._want_mic
        self._start_mic_on_ready = resume
        self._set_capture(False)
        self._overlay.set_listen_enabled(False)
        self._overlay.set_status("loading")
        threading.Thread(target=self._load_model, name="asr-reload", daemon=True).start()

    def _on_ollama_changed(self, name: str) -> None:
        if self._booting:
            return
        self._settings.ollama_model = name
        self._persist_settings()
        threading.Thread(
            target=self._corrector.ensure_loaded, name="ollama-load", daemon=True
        ).start()

    def _on_vad_changed(self, enabled: bool) -> None:
        if self._booting:
            return
        self._settings.vad_enabled = enabled
        self._persist_settings()
        if not enabled and self._vad_sleeping:
            self._leave_vad_idle()

    def _on_predict_changed(self, enabled: bool) -> None:
        if self._booting:
            return
        self._settings.predict_enabled = enabled
        self._persist_settings()
        self._overlay.set_predict_enabled(enabled)

    def _on_prediction_requested(self, prefix: str) -> None:
        # Type field only. Voice partials never reach submit_complete.
        if not self._settings.predict_enabled or not self._overlay.type_field_active():
            return
        self._llm.submit_complete(prefix)

    def _on_predicted(self, prefix: str, suffix: str) -> None:
        if self._stopped or not suffix:
            return
        self._overlay.show_prediction(prefix, suffix)

    def _load_ollama_models(self) -> None:
        self._bridge.ollama_models.emit(self._corrector.list_models())
        self._corrector.ensure_loaded()

    def _fill_settings(self, models: object) -> None:
        names = [str(item) for item in models] if isinstance(models, list) else []
        was_booting = self._booting
        self._booting = True
        try:
            self._overlay.settings.set_values(
                language=self._settings.ui_language,
                opacity=self._settings.overlay_opacity,
                whisper=self._settings.whisper_model,
                ollama=self._settings.ollama_model,
                ollama_models=names,
                vad=self._settings.vad_enabled,
                predict=self._settings.predict_enabled,
            )
        finally:
            self._booting = was_booting

    def shutdown(self) -> None:
        if self._stopped:
            return
        self._persist_timer.stop()
        self._persist_settings()
        self._stopped = True
        if self._meeting is not None:
            self._stop_meeting(restore_mic=False)
        self._focus_timer.stop()
        self._hotkeys.stop()
        self._probe.stop()
        self._asr.shutdown()
        self._capture.close()
        self._llm.shutdown()
        self._history.close()
        if self._tray is not None:
            self._tray.hide()
        self._overlay.hide()
        self._overlay.close()
        from personalclipboard.instance import release_owned

        release_owned()


def main(settings: Settings | None = None) -> int:
    """Boot Qt, overlay, hotkeys, and workers. Replaces any running instance."""
    from personalclipboard.asr.cuda_runtime import configure_cuda12_dlls
    from personalclipboard.instance import install_single_instance

    _install_fault_log()
    configure_cuda12_dlls()
    settings = settings or load_settings()
    qt = QApplication(sys.argv)
    qt.setApplicationName("PersonalClipboard")
    qt.setQuitOnLastWindowClosed(False)  # Hide is not Exit; the tray owns the process
    install_single_instance(qt)
    app = PersonalClipboardApp(qt, settings)
    qt.aboutToQuit.connect(app.shutdown)
    return int(qt.exec())


_FAULT_LOG: list[object] = []  # keep the handle alive; faulthandler does not own it


def _install_fault_log() -> None:
    """Write native crashes next to settings (pythonw has no console)."""
    import faulthandler

    from personalclipboard.config import data_dir

    handle = (data_dir() / "fault.log").open("ab")
    faulthandler.enable(file=handle, all_threads=True)
    _FAULT_LOG.append(handle)


if __name__ == "__main__":
    raise SystemExit(main())
