from __future__ import annotations

import os

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        existing.setQuitOnLastWindowClosed(False)
        return existing
    app = QApplication(["personalclipboard-tests"])
    app.setQuitOnLastWindowClosed(False)
    return app
