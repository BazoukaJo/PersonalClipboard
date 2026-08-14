$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$py = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "Create .venv and pip install -e . first."
}

& $py -m pip install -q pyinstaller
& $py packaging\write_icon.py
& (Join-Path (Get-Location) ".venv\Scripts\pyinstaller.exe") --noconfirm --clean packaging\PersonalClipboard.spec
& $py scripts\write_shortcut.py

$exe = Join-Path (Get-Location) "dist\PersonalClipboard\PersonalClipboard.exe"
if (-not (Test-Path $exe)) {
    throw "Build finished but $exe is missing."
}
Write-Host "Built $exe"
