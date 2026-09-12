"""Unit tests for RetroDeckAdapter."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from romm_steam_sync.adapters.retroarch.base import RetroArchFlavor
from romm_steam_sync.adapters.retroarch.retrodeck import (
    RetroDeckAdapter,
    RetroDeckConfigHealth,
)


def test_retrodeck_adapter_properties():
    """Verify RetroDeckAdapter properties and constants."""
    adapter = RetroDeckAdapter()
    assert adapter.flavor == RetroArchFlavor.RETRODECK
    assert adapter.flavor_name == "RetroDECK"
    assert adapter.FLATPAK_APP_ID == "net.retrodeck.retrodeck"
    assert adapter.get_default_sort_by_content() is True


def test_retrodeck_adapter_health_absent(tmp_path):
    """Verify health returns ABSENT when retrodeck.json is not found."""
    adapter = RetroDeckAdapter(os_platform="linux", home_dir=tmp_path)
    assert adapter.config_health() == RetroDeckConfigHealth.ABSENT


def test_retrodeck_adapter_health_ok(tmp_path):
    """Verify health returns OK when retrodeck.json is valid and directory exists."""
    rd_home = tmp_path / "retrodeck_data"
    rd_home.mkdir()

    cfg_dir = tmp_path / ".var" / "app" / "net.retrodeck.retrodeck" / "config" / "retrodeck"
    cfg_dir.mkdir(parents=True)
    cfg_file = cfg_dir / "retrodeck.json"
    cfg_file.write_text(json.dumps({"paths": {"rd_home_path": str(rd_home)}}))

    adapter = RetroDeckAdapter(os_platform="linux", home_dir=tmp_path)
    health = adapter.config_health()
    assert health == RetroDeckConfigHealth.OK

    # Verify parsed data
    data = adapter.load_retrodeck_config()
    assert data.get("paths", {}).get("rd_home_path") == str(rd_home)


def test_retrodeck_adapter_health_unreadable(tmp_path):
    """Verify health returns UNREADABLE when retrodeck.json contains invalid JSON."""
    cfg_dir = tmp_path / ".var" / "app" / "net.retrodeck.retrodeck" / "config" / "retrodeck"
    cfg_dir.mkdir(parents=True)
    cfg_file = cfg_dir / "retrodeck.json"
    cfg_file.write_text("{invalid json")

    adapter = RetroDeckAdapter(os_platform="linux", home_dir=tmp_path)
    assert adapter.config_health() == RetroDeckConfigHealth.UNREADABLE


def test_retrodeck_adapter_resolve_saves_base_dir_from_config(tmp_path):
    """Verify saves base dir is resolved inside retrodeck_home."""
    rd_home = tmp_path / "retrodeck_data"
    rd_home.mkdir()
    saves_dir = rd_home / "saves"
    saves_dir.mkdir()

    cfg_dir = tmp_path / ".var" / "app" / "net.retrodeck.retrodeck" / "config" / "retrodeck"
    cfg_dir.mkdir(parents=True)
    cfg_file = cfg_dir / "retrodeck.json"
    cfg_file.write_text(json.dumps({"paths": {"rd_home_path": str(rd_home), "saves_path": str(saves_dir)}}))

    adapter = RetroDeckAdapter(os_platform="linux", home_dir=tmp_path)
    resolved = adapter.resolve_saves_base_dir()
    assert resolved == saves_dir.resolve()


def test_retrodeck_adapter_build_launch_command(tmp_path):
    """Verify launch command is structured via Flatpak runner."""
    adapter = RetroDeckAdapter(os_platform="linux", home_dir=tmp_path)
    cmd = adapter.build_launch_command(
        rom_path="/home/deck/retrodeck/roms/gba/Pokemon.gba",
        core_path="/app/lib/libretro/mgba_libretro.so",
    )
    assert cmd[0] == "flatpak"
    assert cmd[1] == "run"
    assert "net.retrodeck.retrodeck" in cmd
    assert "--open" in cmd
    assert "retroarch" in cmd
    assert "-L" in cmd
    assert "/app/lib/libretro/mgba_libretro.so" in cmd
    assert "/home/deck/retrodeck/roms/gba/Pokemon.gba" in cmd


def test_retrodeck_adapter_in_sandbox_binary_resolution(tmp_path):
    """Verify in-sandbox detection checks RetroDECK component path."""
    adapter = RetroDeckAdapter(os_platform="linux", home_dir=tmp_path)

    expected_path = Path("/app/retrodeck/components/retroarch/bin/retroarch")

    with patch("os.path.exists", return_value=True), patch(
        "pathlib.Path.is_file", autospec=True
    ) as mock_is_file:

        def _fake_is_file(p):
            return getattr(p, "as_posix", lambda: str(p))() == "/app/retrodeck/components/retroarch/bin/retroarch"

        mock_is_file.side_effect = _fake_is_file

        resolved = adapter.resolve_binary()
        assert resolved == expected_path.resolve()

        cmd = adapter.build_launch_command(
            rom_path="/home/deck/retrodeck/roms/gba/Pokemon.gba",
            core_path="/app/lib/libretro/mgba_libretro.so",
        )
        assert cmd == [
            str(expected_path),
            "-L",
            "/app/lib/libretro/mgba_libretro.so",
            "/home/deck/retrodeck/roms/gba/Pokemon.gba",
        ]


def test_retrodeck_adapter_prepare_launch_environment_sanitizes_ld_library_path(monkeypatch, tmp_path):
    """Verify RetroDECK launch environment strips PyInstaller temporary extraction directory."""
    fake_meipass = tmp_path / "_MEI000018bclp0Mqq"
    fake_meipass.mkdir()
    monkeypatch.setattr("sys._MEIPASS", str(fake_meipass), raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", str(fake_meipass))

    adapter = RetroDeckAdapter(os_platform="linux", home_dir=tmp_path)
    env = adapter.prepare_launch_environment(
        rom_path="/home/deck/retrodeck/roms/gba/GoldenSun.gba",
        core_path="/app/lib/libretro/mgba_libretro.so",
    )
    assert "LD_LIBRARY_PATH" not in env

