# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for romm-steam-sync main standalone executable."""

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

block_cipher = None

datas = []
datas += collect_data_files("customtkinter")

# Bundle pre-built launcher binary into main executable if available.
# Only consider candidates that match the current build platform so that a
# Windows PE binary is never bundled into a Linux build (and vice versa).
import sys as _sys
if _sys.platform == "win32":
    launcher_candidates = [
        Path("dist/windows/romm-steam-sync-launcher.exe"),
        Path("dist/romm-steam-sync-launcher.exe"),
    ]
else:
    launcher_candidates = [
        Path("dist/linux/romm-steam-sync-launcher"),
        Path("dist/romm-steam-sync-launcher"),
    ]
for candidate in launcher_candidates:
    if candidate.is_file():
        datas.append((str(candidate), "."))
        break

binaries = []
binaries += collect_dynamic_libs("PIL")

hiddenimports = []
hiddenimports += collect_submodules("romm_steam_sync")
hiddenimports += collect_submodules("py7zr")
hiddenimports += collect_submodules("pydantic")
hiddenimports += [
    "customtkinter",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "PIL._imagingtk",
    "PIL._tkinter_finder",
    "tkinter",
    "vdf",
    "psutil",
    "sqlite3",
]

a = Analysis(
    ["src/romm_steam_sync/__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["context", "tests", "pytest", "_pytest", "unittest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="romm-steam-sync",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
