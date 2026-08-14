"""Put CUDA 12 DLLs on PATH so CTranslate2 can LoadLibrary cublas64_12.dll.

The system toolkit is CUDA 13 (cublas64_13.dll). faster-whisper's Windows wheel
is built against CUDA 12, so nvidia-*-cu12 packages must be visible on PATH —
os.add_dll_directory alone is not enough for CTranslate2's native loader.
"""

from __future__ import annotations

import os
import sys

_CONFIGURED = {"done": False}


def configure_cuda12_dlls() -> list[str]:
    """Prepend nvidia-*-cu12 bin dirs to PATH. Safe to call more than once."""
    bin_dirs: list[str] = []
    for pkg_name in (
        "nvidia.cublas",
        "nvidia.cudnn",
        "nvidia.cuda_nvrtc",
        "nvidia.cuda_runtime",
    ):
        try:
            mod = __import__(pkg_name, fromlist=["__path__"])
        except ImportError:
            continue
        pkg_dir = next(iter(getattr(mod, "__path__", [])), None)
        if not pkg_dir:
            continue
        candidate = os.path.join(pkg_dir, "bin" if sys.platform == "win32" else "lib")
        if os.path.isdir(candidate):
            bin_dirs.append(candidate)

    if not bin_dirs:
        return []

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
    elif not _CONFIGURED["done"]:
        existing = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(
            bin_dirs + ([existing] if existing else [])
        )

    _CONFIGURED["done"] = True
    return bin_dirs
