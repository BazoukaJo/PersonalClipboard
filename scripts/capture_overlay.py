"""Render the compact HUD to docs/images/overlay.png for the README."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_OPENGL", "software")

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from personalclipboard.ui.overlay import Overlay

_ROOT = Path(__file__).resolve().parents[1]
_OUT = _ROOT / "docs" / "images" / "overlay.png"


def _stage(overlay: Overlay) -> None:
    overlay.set_listen_enabled(True)
    overlay.set_enable_checked(True)
    overlay.set_status("locked")
    overlay.show_partial("the light is too harsh on the character")
    overlay.show_audio_phrase("The light is too harsh on the character.")
    overlay.set_typed("")
    overlay.resize(520, max(overlay.sizeHint().height(), 280))


def _save(overlay: Overlay) -> None:
    overlay.adjustSize()
    overlay.resize(520, max(overlay.height(), overlay.sizeHint().height(), 280))
    overlay.repaint()
    pad = 40
    canvas = QPixmap(overlay.width() + pad * 2, overlay.height() + pad * 2)
    canvas.fill(QColor(24, 26, 30))
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    overlay.render(painter, QPoint(pad, pad))
    painter.end()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(_OUT), "PNG"):
        raise SystemExit(f"Could not write {_OUT}")
    print(_OUT)


def main() -> int:
    app = QApplication(sys.argv)
    overlay = Overlay()
    overlay.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    _stage(overlay)
    overlay.show()
    app.processEvents()

    def finish() -> None:
        _save(overlay)
        app.quit()

    QTimer.singleShot(250, finish)
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
