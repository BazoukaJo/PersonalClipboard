"""Put bundled CUDA 12 DLLs on PATH before CTranslate2 can LoadLibrary.

PyInstaller 6 onedir sets sys._MEIPASS to the `_internal` folder next to the exe.
"""

from __future__ import annotations

import os
import sys


def _prepend(path: str) -> None:
    if not path or not os.path.isdir(path):
        return
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    if path not in parts:
        os.environ["PATH"] = path + os.pathsep + current if current else path
    if sys.platform == "win32":
        adder = getattr(os, "add_dll_directory", None)
        if adder is not None:
            try:
                adder(path)
            except (OSError, FileNotFoundError):
                pass


_root = getattr(sys, "_MEIPASS", "") or os.path.dirname(sys.executable)
_prepend(_root)
for _rel in (
    os.path.join("nvidia", "cublas", "bin"),
    os.path.join("nvidia", "cudnn", "bin"),
    os.path.join("nvidia", "cuda_nvrtc", "bin"),
    os.path.join("nvidia", "cuda_runtime", "bin"),
):
    _prepend(os.path.join(_root, _rel))
