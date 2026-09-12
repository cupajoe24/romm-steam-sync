"""Unit tests for SteamRetroArchAdapter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from romm_steam_sync.adapters.retroarch.base import RetroArchFlavor
from romm_steam_sync.adapters.retroarch.steam import SteamRetroArchAdapter


def test_steam_adapter_properties():
    """Verify core properties of SteamRetroArchAdapter."""
    adapter = SteamRetroArchAdapter()
    assert adapter.flavor == RetroArchFlavor.STEAM
    assert adapter.flavor_name == "RetroArch Steam"
    assert adapter.STEAM_APP_ID == 1118310


def test_steam_adapter_resolve_binary_from_configured_path(tmp_path):
    """Verify configured path takes precedence when resolving binary."""
    ra_exe = tmp_path / "retroarch.exe"
    ra_exe.write_text("dummy")

    adapter = SteamRetroArchAdapter(configured_path=str(ra_exe), os_platform="win32")
    assert adapter.resolve_binary() == ra_exe.resolve()


def test_steam_adapter_resolve_binary_from_steam_root(tmp_path):
    """Verify resolving binary from Steam root library folder."""
    steam_root = tmp_path / "Steam"
    ra_dir = steam_root / "steamapps" / "common" / "RetroArch"
    ra_dir.mkdir(parents=True)
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.write_text("dummy")

    adapter = SteamRetroArchAdapter(os_platform="win32")
    with patch("romm_steam_sync.adapters.steam_path.SteamPathResolver.get_steam_root", return_value=steam_root):
        resolved = adapter.resolve_binary()
        assert resolved == ra_exe.resolve()


def test_steam_adapter_get_core_search_dirs(tmp_path):
    """Verify core search directories include Steam RetroArch cores folder."""
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.write_text("dummy")
    cores_dir = ra_dir / "cores"
    cores_dir.mkdir()

    adapter = SteamRetroArchAdapter(configured_path=str(ra_exe), os_platform="win32")
    dirs = adapter.get_core_search_dirs()
    assert any(cores_dir.resolve() == d.resolve() for d in dirs)


def test_steam_adapter_build_launch_command_windows(tmp_path):
    """Verify building launch command on Windows does direct process invocation."""
    ra_exe = tmp_path / "retroarch.exe"
    ra_exe.write_text("dummy")
    core_dll = tmp_path / "cores" / "snes9x_libretro.dll"

    adapter = SteamRetroArchAdapter(configured_path=str(ra_exe), os_platform="win32")
    cmd = adapter.build_launch_command(
        rom_path="C:/roms/mario.sfc",
        core_path=str(core_dll),
        binary_path=ra_exe,
    )
    assert cmd[0] == str(ra_exe)
    assert cmd[1] == "-L"
    assert cmd[2] == str(core_dll)
    assert cmd[3] == "C:/roms/mario.sfc"


def test_steam_adapter_build_launch_command_linux(tmp_path):
    """Verify building launch command on Linux uses Steam Linux Runtime runner."""
    ra_bin = tmp_path / "retroarch"
    ra_bin.write_text("dummy")
    core_so = tmp_path / "cores" / "snes9x_libretro.so"

    runner_script = tmp_path / "run-in-sniper"
    runner_script.write_text("#!/bin/sh\n")

    wrapper_script = tmp_path / "run_retroarch.sh"
    wrapper_script.write_text("#!/bin/sh\n")

    adapter = SteamRetroArchAdapter(configured_path=str(ra_bin), os_platform="linux")
    with patch.object(adapter, "resolve_steam_linux_runtime", return_value=runner_script), \
         patch.object(adapter, "get_or_create_retroarch_wrapper", return_value=str(wrapper_script)):
        cmd = adapter.build_launch_command(
            rom_path="/home/deck/roms/mario.sfc",
            core_path=str(core_so),
            binary_path=ra_bin,
        )
        assert cmd[0] == str(runner_script)
        assert "--" in cmd
        assert str(wrapper_script) in cmd
