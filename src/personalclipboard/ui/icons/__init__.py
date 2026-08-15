"""Vendored Lucide SVGs rendered with QtSvg. Offline; no network."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QByteArray, QRectF, QSize
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QApplication

from personalclipboard.ui.theme import TEXT

_DIR = Path(__file__).resolve().parent


def make_icon(name: str, size: int = 16, color: str = TEXT) -> QIcon:
    icon = QIcon()
    icon.addPixmap(make_pixmap(name, size, color))
    return icon


def make_pixmap(name: str, size: int = 16, color: str = TEXT) -> QPixmap:
    return _render_pixmap(name, size, color, _device_pixel_ratio())


def icon_size(side: int = 16) -> QSize:
    return QSize(side, side)


def _device_pixel_ratio() -> float:
    app = QApplication.instance()
    if app is None or not isinstance(app, QApplication):
        return 1.0
    screen = app.primaryScreen()
    if screen is None:
        return 1.0
    return max(1.0, float(screen.devicePixelRatio()))


@lru_cache(maxsize=64)
def _render_pixmap(name: str, size: int, color: str, dpr: float) -> QPixmap:
    path = _DIR / f"{name}.svg"
    if not path.is_file():
        return QPixmap()
    raw = path.read_text(encoding="utf-8").replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(raw.encode("utf-8")))
    if not renderer.isValid():
        return QPixmap()
    side = max(1, int(round(max(1, size) * dpr)))
    pixmap = QPixmap(side, side)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, float(side), float(side)))
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap
