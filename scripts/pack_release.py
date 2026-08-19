"""Zip dist/PersonalClipboard for a GitHub Release.

GitHub caps each asset at 2 GiB, so CUDA 12 DLLs are a second zip. Unzip both
into the same folder; the CUDA zip adds PersonalClipboard/_internal/nvidia.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DIST = _ROOT / "dist" / "PersonalClipboard"
_OUT = _ROOT / "release"
_APP = "PersonalClipboard-0.3.2-windows-x64.zip"
_CUDA = "PersonalClipboard-0.3.2-windows-x64-cuda12.zip"
_README = """PersonalClipboard v0.3.2

1. Unzip PersonalClipboard-0.3.2-windows-x64.zip
2. Unzip PersonalClipboard-0.3.2-windows-x64-cuda12.zip into the same folder
   (it adds PersonalClipboard\\_internal\\nvidia).
3. Install Ollama for Windows and run:
     ollama pull qwen2.5:1.5b
4. Run PersonalClipboard\\PersonalClipboard.exe

NVIDIA driver must be CUDA 12 capable. Whisper weights download on first launch.
Audio, transcripts, and clipboard text stay on this PC.
"""


def _is_nvidia(rel: Path) -> bool:
    return "nvidia" in rel.parts


def _zip_files(target: Path, files: list[tuple[Path, str]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        target.unlink()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        for src, arc in files:
            zf.write(src, arc)
    print(f"{target} ({target.stat().st_size} bytes, {len(files)} files)")


def main() -> int:
    if not (_DIST / "PersonalClipboard.exe").is_file():
        raise SystemExit(f"missing {_DIST / 'PersonalClipboard.exe'}; run scripts\\build_exe.ps1")
    app_files: list[tuple[Path, str]] = []
    cuda_files: list[tuple[Path, str]] = []
    for path in _DIST.rglob("*"):
        if not path.is_file():
            continue
        rel = Path("PersonalClipboard") / path.relative_to(_DIST)
        arc = rel.as_posix()
        if _is_nvidia(rel):
            cuda_files.append((path, arc))
        else:
            app_files.append((path, arc))
    readme = _OUT / "_zip_readme.txt"
    _OUT.mkdir(parents=True, exist_ok=True)
    readme.write_text(_README, encoding="utf-8")
    app_files.append((readme, "PersonalClipboard/README.txt"))
    _zip_files(_OUT / _APP, app_files)
    _zip_files(_OUT / _CUDA, cuda_files)
    readme.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
