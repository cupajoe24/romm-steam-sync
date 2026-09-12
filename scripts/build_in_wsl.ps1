# Build automation script to compile Linux standalone executables inside WSL2
$ErrorActionPreference = "Stop"

Write-Host "[romm-steam-sync] Starting Linux standalone executable build in WSL..." -ForegroundColor Cyan

# Check if WSL is available
if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    Write-Error "WSL is not available on this machine. Please install WSL2."
    exit 1
}

# Resolve workspace path in WSL format
$winPath = (Get-Item .).FullName
$driveLetter = $winPath.Substring(0, 1).ToLower()
$restOfPath = $winPath.Substring(2).Replace('\', '/')
$wslPath = "/mnt/$driveLetter$restOfPath"

Write-Host "[romm-steam-sync] Workspace WSL Path: $wslPath"

$wslScript = @"
set -e
cd '$wslPath'

if [ ! -d '.venv_linux' ]; then
    echo '[WSL] Creating Linux virtual environment in .venv_linux...'
    python3.9 -m venv .venv_linux
fi

echo '[WSL] Installing/upgrading dependencies in .venv_linux...'
.venv_linux/bin/python -m pip install --upgrade pip setuptools wheel
.venv_linux/bin/python -m pip install -e '.[dev]' pyinstaller

echo '[WSL] Running scripts/build_linux_bin.py...'
.venv_linux/bin/python scripts/build_linux_bin.py
"@

wsl bash -c "$wslScript"

Write-Host "[romm-steam-sync] Linux build process completed successfully!" -ForegroundColor Green
