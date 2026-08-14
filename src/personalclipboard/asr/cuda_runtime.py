"""Put CUDA 12 DLLs on PATH so CTranslate2 can LoadLibrary cublas64_12.dll.

The system toolkit is CUDA 13 (cublas64_13.dll). faster-whisper's Windows wheel
is built against CUDA 12, so nvidia-*-cu12 packages must be visible on PATH —
os.add_dll_directory alone is not enough for CTranslate2's native loader.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_CONFIGURED = {"done": False}
_NVIDIA_PKGS = (
    "nvidia.cublas",
    "nvidia.cudnn",
    "nvidia.cuda_nvrtc",
    "nvidia.cuda_runtime",
)
_FROZEN_RELS = (
    # PyInstaller 6 onedir: sys._MEIPASS is dist/.../_internal.
    "",
    os.path.join("nvidia", "cublas", "bin"),
    os.path.join("nvidia", "cudnn", "bin"),
    os.path.join("nvidia", "cuda_nvrtc", "bin"),
    os.path.join("nvidia", "cuda_runtime", "bin"),
)


def configure_cuda12_dlls() -> list[str]:
    """Prepend nvidia-*-cu12 bin dirs to PATH. Safe to call more than once."""
    bin_dirs = _wheel_bin_dirs() or _frozen_bin_dirs()
    if not bin_dirs:
        return []
    _apply_bin_dirs(bin_dirs)
    _CONFIGURED["done"] = True
    return bin_dirs


def _wheel_bin_dirs() -> list[str]:
    found: list[str] = []
    sub = "bin" if sys.platform == "win32" else "lib"
    for pkg_name in _NVIDIA_PKGS:
        try:
            mod = __import__(pkg_name, fromlist=["__path__"])
        except ImportError:
            continue
        pkg_dir = next(iter(getattr(mod, "__path__", [])), None)
        if not pkg_dir:
            continue
        candidate = os.path.join(pkg_dir, sub)
        if os.path.isdir(candidate):
            found.append(candidate)
    return found


def _frozen_bin_dirs() -> list[str]:
    if not getattr(sys, "frozen", False):
        return []
    frozen_root = getattr(sys, "_MEIPASS", "") or str(Path(sys.executable).resolve().parent)
    found: list[str] = []
    for rel in _FROZEN_RELS:
        candidate = os.path.join(frozen_root, rel) if rel else frozen_root
        if os.path.isdir(candidate):
            found.append(candidate)
    return found


def _apply_bin_dirs(bin_dirs: list[str]) -> None:
    if sys.platform == "win32":
        current = os.environ.get("PATH", "")
        prefix = os.pathsep.join(bin_dirs)
        if prefix not in current:
            os.environ["PATH"] = prefix + os.pathsep + current
        for directory in bin_dirs:
            try:
                os.add_dll_directory(directory)
            except (OSError, FileNotFoundError):
                continue
        return
    if _CONFIGURED["done"]:
        return
    existing = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(
        bin_dirs + ([existing] if existing else [])
    )
