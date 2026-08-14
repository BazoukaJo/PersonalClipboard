"""Point the local desktop shortcut at dist/PersonalClipboard/PersonalClipboard.exe."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def shortcut_targets() -> list[Path]:
    home = Path.home()
    names = [
        home / "OneDrive" / "Bureau" / "PersonalClipboard.lnk",
        home / "OneDrive" / "Desktop" / "PersonalClipboard.lnk",
        home / "Desktop" / "PersonalClipboard.lnk",
    ]
    found = [path for path in names if path.is_file()]
    if found:
        return found
    bureau = home / "OneDrive" / "Bureau"
    if bureau.is_dir():
        return [bureau / "PersonalClipboard.lnk"]
    desktop = home / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    return [desktop / "PersonalClipboard.lnk"]


def write_shortcut(lnk: Path, exe: Path) -> None:
    work = str(exe.parent)
    target = str(exe)
    link = str(lnk)
    # Clear Arguments: an old pythonw shortcut still has `-m personalclipboard`.
    script = (
        "$s = New-Object -ComObject WScript.Shell\n"
        f"$l = $s.CreateShortcut('{link.replace(chr(39), chr(39)+chr(39))}')\n"
        f"$l.TargetPath = '{target.replace(chr(39), chr(39)+chr(39))}'\n"
        f"$l.WorkingDirectory = '{work.replace(chr(39), chr(39)+chr(39))}'\n"
        "$l.Arguments = ''\n"
        "$l.WindowStyle = 1\n"
        f"$l.IconLocation = '{target.replace(chr(39), chr(39)+chr(39))},0'\n"
        "$l.Description = 'PersonalClipboard'\n"
        "$l.Save()\n"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=True,
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    exe = root / "dist" / "PersonalClipboard" / "PersonalClipboard.exe"
    if not exe.is_file():
        print(f"missing {exe}", file=sys.stderr)
        return 1
    for lnk in shortcut_targets():
        lnk.parent.mkdir(parents=True, exist_ok=True)
        write_shortcut(lnk, exe)
        print(lnk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
