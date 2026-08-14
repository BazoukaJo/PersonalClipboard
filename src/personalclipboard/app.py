"""QApplication lifecycle, tray, and worker start/stop."""

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QScreen
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from personalclipboard.asr.engine import AsrEngine
from personalclipboard.audio.capture import AudioCapture
from personalclipboard.clipboard.service import ClipboardService
from personalclipboard.config import Settings, default_settings
from personalclipboard.hotkeys.bindings import GlobalHotkeys
from personalclipboard.llm.corrector import Corrector
from personalclipboard.llm.worker import LlmWorker
from personalclipboard.notes.meeting import MeetingNotes, desktop_directory
from personalclipboard.ui.bridge import UiBridge
from personalclipboard.ui.copy_cue import play_copy_cue
from personalclipboard.ui.overlay import Overlay
from personalclipboard.ui.tray import make_tray_icon, show_about, spawn_new_instance
from personalclipboard.windows.input import WindowInput


class PersonalClipboardApp:
    def __init__(self, qt: QApplication, settings: Settings) -> None:
        self._bridge = UiBridge()
        self._capture = AudioCapture(settings)
        self._asr = AsrEngine(
            settings,
            self._capture.ring,
            on_partial=self._bridge.partial.emit,
            on_commit=self._bridge.commit.emit,
            on_status=self._bridge.status.emit,
            on_error=self._bridge.error.emit,
            on_command=self._bridge.command.emit,
        )
        self._corrector = Corrector(settings)
        self._llm = LlmWorker(self._corrector, lambda _jid, text: self._bridge.corrected.emit(text))
        self._overlay = Overlay()
        clipboard = qt.clipboard()
        if clipboard is None:
            raise RuntimeError("Qt clipboard is unavailable")
        self._clipboard = ClipboardService(clipboard)
        self._hotkeys = GlobalHotkeys(settings, self._bridge.reformat_requested.emit)
        self._windows = WindowInput()
        self._last_ready = ""
        self._commit_source = "audio"
        self._typed_original = ""
        self._stopped = False
        self._meeting: MeetingNotes | None = None
        self._meeting_owned_capture = False
        self._qt = qt
        self._tray: QSystemTrayIcon | None = None
        self._tray_menu: QMenu | None = None
        self._focus_timer = QTimer(qt)
        self._focus_timer.setInterval(200)
        self._focus_timer.timeout.connect(self._windows.poll)
        self._focus_timer.start()
        self._connect_signals(qt)
        self._overlay.set_listen_enabled(False)
        self._overlay.set_status("loading")
        self._overlay.set_message("Loading Whisper on CUDA…")
        self._place_overlay(qt)
        self._overlay.show()
        threading.Thread(target=self._load_model, name="asr-load", daemon=True).start()
        try:
            self._hotkeys.start()
        except Exception as exc:
            self._overlay.set_message(f"Hotkey failed: {exc}")

    def _connect_signals(self, qt: QApplication) -> None:
        self._bridge.partial.connect(self._overlay.show_partial)
        self._bridge.status.connect(self._overlay.set_status)
        self._bridge.commit.connect(self._on_speech_commit)
        self._bridge.corrected.connect(self._on_corrected)
        self._bridge.error.connect(self._on_error)
        self._bridge.model_ready.connect(self._on_model_ready)
        self._bridge.reformat_requested.connect(self._on_reformat)
        self._bridge.command.connect(self._on_command)
        self._overlay.enable_toggled.connect(self._set_capture)
        self._overlay.hide_requested.connect(self._overlay.hide)
        self._overlay.copy_requested.connect(self._copy_ready)
        self._overlay.phrase_completed.connect(self._on_typed_commit)
        self._overlay.meeting_toggled.connect(self._on_meeting_toggled)
        self._init_tray(qt)

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
        self.shutdown()
        spawn_new_instance()
        self._qt.quit()

    def _show_overlay(self) -> None:
        self._overlay.show()
        self._overlay.raise_()

    def _place_overlay(self, qt: QApplication) -> None:
        screen = qt.primaryScreen()
        if screen is None:
            return
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
            self._overlay.set_enable_checked(True)
            self._set_capture(True)
            return
        self._overlay.set_status("error")
        self._overlay.set_message(self._asr.load_error or "CUDA Whisper unavailable")
        self._overlay.set_listen_enabled(False)

    def _set_capture(self, enabled: bool) -> None:
        if enabled:
            if not self._asr.ready:
                self._overlay.set_enable_checked(False)
                self._overlay.set_message("Waiting for Whisper to load…")
                return
            try:
                self._capture.start()
                self._asr.start()
            except Exception as exc:
                self._overlay.set_enable_checked(False)
                self._overlay.set_status("error")
                self._overlay.set_message(str(exc))
                self._capture.stop()
                return
            self._overlay.set_status("listening")
            mic = self._capture.device_name or "microphone"
            self._overlay.set_message(f"Listening on {mic}. Finish with a period to copy.")
            return
        if self._meeting is not None:
            self._stop_meeting(restore_mic=False)
        self._asr.stop()
        self._capture.stop()
        self._overlay.set_status("off")
        self._overlay.show_partial("")
        self._overlay.set_message("Mic off. Check Mic to listen.")

    def _on_speech_commit(self, text: str) -> None:
        if self._meeting is not None:
            self._meeting.append(text)
            self._overlay.show_meeting_notes(self._meeting.preview())
            return
        self._finish_phrase(text, "audio")

    def _on_typed_commit(self, text: str) -> None:
        self._finish_phrase(text, "typed")

    def _finish_phrase(self, text: str, source: str) -> None:
        if not any(char.isalnum() for char in text):
            return
        self._commit_source = source
        if source == "typed":
            self._typed_original = text
            self._overlay.show_typed_phrase(text)
        else:
            self._overlay.show_audio_phrase(text)
        self._overlay.set_message("Correcting…")
        self._llm.submit(text)

    def _on_corrected(self, text: str) -> None:
        if self._stopped or not text.strip():
            return
        self._last_ready = text
        self._clipboard.write(text)
        if self._commit_source == "typed":
            self._overlay.show_typed_phrase(text)
            self._overlay.apply_typed_correction(self._typed_original, text)
        else:
            self._overlay.show_audio_phrase(text)
        self._overlay.set_message("On clipboard. Press Ctrl+V to paste.")

    def _on_reformat(self) -> None:
        current = self._clipboard.read()
        if not current.strip():
            self._overlay.set_message("Clipboard is empty")
            return
        self._overlay.set_message("Correcting clipboard…")
        self._commit_source = "typed"
        self._typed_original = current
        self._llm.submit(current)

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
        self._overlay.show_typed_phrase(text)
        self._overlay.set_typed(text)
        self._overlay.set_message("Copied selection from the other window.")
        play_copy_cue()

    def _on_error(self, message: str) -> None:
        self._overlay.set_message(message)

    def _on_meeting_toggled(self, want: bool) -> None:
        if want:
            self._start_meeting()
            return
        self._stop_meeting()

    def _start_meeting(self) -> None:
        if self._meeting is not None:
            return
        if not self._asr.ready:
            self._overlay.set_message("Waiting for Whisper to load…")
            return
        owned = False
        if not self._capture.active:
            try:
                self._capture.start()
                self._asr.start()
            except Exception as exc:
                self._overlay.set_message(str(exc))
                return
            owned = True
            self._overlay.set_enable_checked(True)
        self._capture.ring.clear()
        self._asr.set_meeting_mode(True)
        source = self._capture.device_name or "microphone"
        try:
            notes = MeetingNotes(desktop_directory(), datetime.now(), source)
        except OSError as exc:
            self._asr.set_meeting_mode(False)
            if owned:
                self._overlay.set_enable_checked(False)
                self._set_capture(False)
            self._overlay.set_message(f"Could not create notes file: {exc}")
            return
        self._meeting = notes
        self._meeting_owned_capture = owned
        self._overlay.set_meeting_recording(True, notes.filename)
        self._overlay.set_status("recording")
        self._overlay.set_message(
            f"Recording on {source}. Notes save to the desktop as {notes.filename}."
        )

    def _stop_meeting(self, *, restore_mic: bool = True) -> None:
        notes = self._meeting
        self._meeting = None
        leftover = self._asr.flush_remainder()
        self._asr.set_meeting_mode(False)
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
        self._meeting_owned_capture = False
        if restore_mic and owned:
            self._overlay.set_enable_checked(False)
            self._set_capture(False)
            if saved:
                self._overlay.set_message(f"Meeting notes saved as {saved} on the desktop.")
            return
        if self._capture.active:
            self._overlay.set_status("listening")

    def shutdown(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        if self._meeting is not None:
            self._stop_meeting(restore_mic=False)
        self._focus_timer.stop()
        self._hotkeys.stop()
        self._asr.shutdown()
        self._capture.close()
        self._llm.shutdown()
        if self._tray is not None:
            self._tray.hide()


def main(settings: Settings | None = None) -> int:
    """Boot Qt, overlay, hotkeys, and workers. Starts listening once Whisper is ready."""
    from personalclipboard.asr.cuda_runtime import configure_cuda12_dlls

    configure_cuda12_dlls()
    settings = settings or default_settings()
    qt = QApplication(sys.argv)
    qt.setApplicationName("PersonalClipboard")
    qt.setQuitOnLastWindowClosed(False)
    app = PersonalClipboardApp(qt, settings)
    qt.aboutToQuit.connect(app.shutdown)
    return int(qt.exec())


if __name__ == "__main__":
    raise SystemExit(main())
