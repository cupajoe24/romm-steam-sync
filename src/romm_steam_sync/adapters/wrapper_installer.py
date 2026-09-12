"""Wrapper binary and script installer for romm-steam-sync launcher."""

import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Optional

from romm_steam_sync.config import get_default_config_dir

logger = logging.getLogger(__name__)


def _is_platform_native_binary(path: Path) -> bool:
    """Return True if the binary at *path* is native to the current OS.

    Reads the first few magic bytes of the file to distinguish ELF (Linux/macOS)
    from PE (Windows) executables.  A wrong-platform binary would fail with
    'Exec format error' on Linux or be silently ignored on Windows.

    Args:
        path: Path to the binary to inspect.

    Returns:
        True if the binary matches the current platform, False otherwise.
    """
    try:
        with open(path, "rb") as fh:
            magic = fh.read(4)
    except OSError as e:
        logger.debug("Cannot read magic bytes from %s: %s", path, e)
        return False

    if os.name == "nt":
        # Windows PE files start with 'MZ'
        return magic[:2] == b"MZ"
    else:
        # ELF files start with \x7fELF
        return magic == b"\x7fELF"


def get_bundled_launcher_path() -> Optional[Path]:
    """Locate bundled romm-steam-sync-launcher executable if present.

    Checks the PyInstaller temporary extraction directory (sys._MEIPASS) and
    the directory containing sys.executable.  Candidates are validated against
    the current platform's binary format (ELF on Linux, PE on Windows) so that
    a Windows executable accidentally bundled into a Linux build is silently
    skipped rather than being installed and causing an 'Exec format error'.

    Returns:
        Path to the bundled launcher binary, or None if not running in a bundle.
    """
    binary_name = (
        "romm-steam-sync-launcher.exe"
        if os.name == "nt"
        else "romm-steam-sync-launcher"
    )
    pattern = (
        "romm-steam-sync-launcher*.exe"
        if os.name == "nt"
        else "romm-steam-sync-launcher*"
    )

    # Check PyInstaller onefile unpacked directory
    if hasattr(sys, "_MEIPASS"):
        meipass_dir = Path(sys._MEIPASS)
        meipass_path = meipass_dir / binary_name
        if meipass_path.is_file() and _is_platform_native_binary(meipass_path):
            return meipass_path
        for candidate in sorted(meipass_dir.glob(pattern)):
            if (
                candidate.is_file()
                and not candidate.name.endswith((".spec", ".tar.gz", ".zip"))
                and _is_platform_native_binary(candidate)
            ):
                return candidate

    # Check directory alongside current executable
    if sys.executable:
        parent_dir = Path(sys.executable).parent
        sibling_path = parent_dir / binary_name
        if sibling_path.is_file() and _is_platform_native_binary(sibling_path):
            return sibling_path
        for candidate in sorted(parent_dir.glob(pattern)):
            if (
                candidate.is_file()
                and not candidate.name.endswith((".spec", ".tar.gz", ".zip"))
                and _is_platform_native_binary(candidate)
            ):
                return candidate

    return None


def get_installed_wrapper_path() -> Path:
    """Get expected absolute path of the launcher wrapper script or executable.

    Returns:
        Path to the wrapper script or installed standalone launcher binary.
    """
    bin_dir = get_default_config_dir() / "bin"
    if os.name == "nt":
        exe_path = bin_dir / "romm-steam-sync-launcher.exe"
        if getattr(sys, "frozen", False) or exe_path.is_file():
            return exe_path
        return bin_dir / "romm-steam-sync-launcher.vbs"
    return bin_dir / "romm-steam-sync-launcher"


def resolve_pythonw_executable() -> str:
    """Find pythonw.exe to prevent command prompt window popping up on Windows.

    Returns:
        Absolute path string to pythonw.exe if available, or sys.executable.
    """
    py_path = Path(sys.executable)
    if os.name == "nt":
        pyw = py_path.parent / "pythonw.exe"
        if pyw.is_file():
            return str(pyw.resolve())
    return str(py_path.resolve())


def install_wrapper() -> Path:
    """Install launcher executable or wrapper script in the user config directory.

    If a bundled launcher executable is available, it is copied into the user's
    config directory (e.g. %APPDATA%/romm-steam-sync/bin). Otherwise, a script
    wrapper is generated for local development.

    Returns:
        Path to the installed launcher executable or wrapper script.
    """
    bin_dir = get_default_config_dir() / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    bundled_launcher = get_bundled_launcher_path()
    if bundled_launcher and bundled_launcher.is_file():
        canonical_name = (
            "romm-steam-sync-launcher.exe"
            if os.name == "nt"
            else "romm-steam-sync-launcher"
        )
        target_path = bin_dir / canonical_name
        try:
            shutil.copy2(bundled_launcher, target_path)
            if os.name != "nt":
                mode = os.stat(target_path).st_mode
                os.chmod(target_path, mode | 0o755)
            logger.info("Installed launcher binary to %s", target_path)
            return target_path
        except Exception as e:
            logger.error(
                "Failed copying launcher executable from %s to %s: %s",
                bundled_launcher,
                target_path,
                e,
            )

    if os.name == "nt" and (bin_dir / "romm-steam-sync-launcher.exe").is_file():
        return bin_dir / "romm-steam-sync-launcher.exe"

    py_exe = resolve_pythonw_executable()

    if os.name == "nt":
        wrapper_path = bin_dir / "romm-steam-sync-launcher.vbs"
        script_content = f'''Set WshShell = CreateObject("WScript.Shell")
args = ""
For Each arg In WScript.Arguments
    args = args & " """ & arg & """"
Next
WshShell.Run """{py_exe}"" -m romm_steam_sync.launcher" & args, 0, False
'''
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        cmd_path = bin_dir / "romm-steam-sync-launcher.cmd"
        cmd_content = f"""@echo off
wscript.exe "%~dp0romm-steam-sync-launcher.vbs" %*
"""
        with open(cmd_path, "w", encoding="utf-8") as f:
            f.write(cmd_content)
        logger.info("Installed Windows launcher wrapper at %s", wrapper_path)
        return wrapper_path
    else:
        wrapper_path = bin_dir / "romm-steam-sync-launcher"
        script_content = f"""#!/bin/sh
exec "{py_exe}" -m romm_steam_sync.launcher "$@"
"""
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        try:
            mode = os.stat(wrapper_path).st_mode
            os.chmod(wrapper_path, mode | 0o755)
            logger.info(
                "Installed Unix launcher wrapper at %s (mode 0755)",
                wrapper_path,
            )
        except Exception as e:
            logger.warning(
                "Failed to set executable mode for wrapper %s: %s",
                wrapper_path,
                e,
            )

        return wrapper_path
