# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for romm-steam-sync-launcher standalone executable."""

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = []
datas += collect_data_files("customtkinter")

hiddenimports = []
hiddenimports += collect_submodules("romm_steam_sync")
hiddenimports += collect_submodules("py7zr")
hiddenimports += collect_submodules("pydantic")
hiddenimports += [
    "customtkinter",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "vdf",
    "psutil",
    "sqlite3",
]

a = Analysis(
    ["src/romm_steam_sync/launcher/__main__.py"],
    pathex=["src"],
    binaries=[],
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
    name="romm-steam-sync-launcher",
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
