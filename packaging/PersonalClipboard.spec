# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec. Whisper weights stay in the Hugging Face cache."""

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
ICON = ROOT / "packaging" / "app.ico"
HOOK = ROOT / "packaging" / "runtime_hook_cuda.py"

datas: list = []
binaries: list = []
hidden: list = collect_submodules("personalclipboard")

for pkg in (
    "faster_whisper",
    "ctranslate2",
    "av",
    "tokenizers",
    "onnxruntime",
    "pyaudio",
    "pynput",
    "huggingface_hub",
):
    try:
        extra_d, extra_b, extra_h = collect_all(pkg)
    except Exception:
        continue
    datas += extra_d
    binaries += extra_b
    hidden += extra_h

for pkg in ("ctranslate2", "av", "tokenizers", "onnxruntime", "pyaudio", "sounddevice"):
    try:
        binaries += collect_dynamic_libs(pkg)
    except Exception:
        pass

for pkg_name, dest in (
    ("nvidia.cublas", "nvidia/cublas/bin"),
    ("nvidia.cudnn", "nvidia/cudnn/bin"),
    ("nvidia.cuda_nvrtc", "nvidia/cuda_nvrtc/bin"),
    ("nvidia.cuda_runtime", "nvidia/cuda_runtime/bin"),
):
    try:
        mod = __import__(pkg_name, fromlist=["__path__"])
    except ImportError:
        continue
    pkg_dir = next(iter(getattr(mod, "__path__", [])), None)
    if not pkg_dir:
        continue
    bin_dir = Path(pkg_dir) / "bin"
    if not bin_dir.is_dir():
        continue
    for dll in bin_dir.glob("*.dll"):
        binaries.append((str(dll), dest))

hidden += [
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtNetwork",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
]

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=sorted(set(hidden)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(HOOK)],
    excludes=["tkinter", "matplotlib", "torch", "tensorflow"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PersonalClipboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ICON) if ICON.is_file() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PersonalClipboard",
)
