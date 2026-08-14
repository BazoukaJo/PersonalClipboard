"""Write packaging/app.ico from the tray glyph."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from personalclipboard.ui.tray import make_tray_icon


def main() -> int:
    _qt = QApplication.instance() or QApplication(sys.argv)
    assert _qt is not None  # QPixmap needs an application
    icon: QIcon = make_tray_icon()
    pix = icon.pixmap(256, 256)
    target = Path(__file__).resolve().parent / "app.ico"
    if not pix.save(str(target), "ICO"):
        print(f"could not write {target}", file=sys.stderr)
        return 1
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
