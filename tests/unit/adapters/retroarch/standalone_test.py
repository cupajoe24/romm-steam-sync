"""Unit tests for StandaloneRetroArchAdapter."""

from pathlib import Path
from unittest.mock import patch

import pytest

from romm_steam_sync.adapters.retroarch.base import RetroArchFlavor
from romm_steam_sync.adapters.retroarch.standalone import StandaloneRetroArchAdapter


def test_standalone_adapter_properties():
    """Verify properties of StandaloneRetroArchAdapter."""
    adapter = StandaloneRetroArchAdapter()
    assert adapter.flavor == RetroArchFlavor.STANDALONE
    assert adapter.flavor_name == "RetroArch Standalone"


def test_standalone_adapter_resolve_binary_from_configured(tmp_path):
    """Verify resolving binary from configured path."""
    ra_exe = tmp_path / "retroarch.exe"
    ra_exe.write_text("dummy")

    adapter = StandaloneRetroArchAdapter(configured_path=str(ra_exe), os_platform="win32")
    assert adapter.resolve_binary() == ra_exe.resolve()


def test_standalone_adapter_resolve_binary_from_system_path(tmp_path):
    """Verify resolving binary from system PATH."""
    ra_bin = tmp_path / "retroarch"
    ra_bin.write_text("dummy")

    adapter = StandaloneRetroArchAdapter(os_platform="linux")
    with patch("shutil.which", return_value=str(ra_bin)):
        resolved = adapter.resolve_binary()
        assert resolved == ra_bin.resolve()


def test_standalone_adapter_resolve_cfg_path_windows(tmp_path):
    """Verify resolving retroarch.cfg on Windows."""
    appdata = tmp_path / "AppData" / "Roaming"
    ra_dir = appdata / "RetroArch"
    ra_dir.mkdir(parents=True)
    cfg_file = ra_dir / "retroarch.cfg"
    cfg_file.write_text("savefile_directory = \"\"\n")

    adapter = StandaloneRetroArchAdapter(os_platform="win32", home_dir=tmp_path)
    with patch.dict("os.environ", {"APPDATA": str(appdata)}):
        resolved = adapter.resolve_cfg_path()
        assert resolved == cfg_file.resolve()


def test_standalone_adapter_get_core_search_dirs_linux(tmp_path):
    """Verify Linux core search directories include ~/.config/retroarch/cores."""
    adapter = StandaloneRetroArchAdapter(os_platform="linux", home_dir=tmp_path)
    dirs = adapter.get_core_search_dirs()
    expected = tmp_path / ".config" / "retroarch" / "cores"
    assert any(d == expected for d in dirs)


def test_standalone_adapter_build_launch_command(tmp_path):
    """Verify building launch command for standalone RetroArch."""
    ra_exe = tmp_path / "retroarch.exe"
    ra_exe.write_text("dummy")
    core = tmp_path / "mgba_libretro.dll"

    adapter = StandaloneRetroArchAdapter(configured_path=str(ra_exe), os_platform="win32")
    cmd = adapter.build_launch_command(
        rom_path="C:/games/zelda.gba",
        core_path=str(core),
        binary_path=ra_exe,
    )
    assert cmd == [str(ra_exe), "-L", str(core), "C:/games/zelda.gba"]
