"""Unit tests for RetroArch flavor detector and factory functions."""

from pathlib import Path
from unittest.mock import patch

import pytest

from romm_steam_sync.adapters.retroarch import (
    RetroArchFlavor,
    RetroDeckAdapter,
    StandaloneRetroArchAdapter,
    SteamRetroArchAdapter,
    detect_retroarch_flavor,
    get_retroarch_adapter,
)


def test_detector_explicit_preference():
    """Verify explicit flavor preferences override heuristics."""
    steam_adapter = detect_retroarch_flavor(preferred_flavor="steam")
    assert isinstance(steam_adapter, SteamRetroArchAdapter)
    assert steam_adapter.flavor == RetroArchFlavor.STEAM

    standalone_adapter = detect_retroarch_flavor(preferred_flavor="standalone")
    assert isinstance(standalone_adapter, StandaloneRetroArchAdapter)
    assert standalone_adapter.flavor == RetroArchFlavor.STANDALONE

    retrodeck_adapter = detect_retroarch_flavor(preferred_flavor="retrodeck")
    assert isinstance(retrodeck_adapter, RetroDeckAdapter)
    assert retrodeck_adapter.flavor == RetroArchFlavor.RETRODECK

    # Test Enum value
    enum_adapter = detect_retroarch_flavor(preferred_flavor=RetroArchFlavor.STEAM)
    assert isinstance(enum_adapter, SteamRetroArchAdapter)


def test_detector_flavor_alias_keyword():
    """Verify 'flavor' keyword works identically to 'preferred_flavor'."""
    adapter = get_retroarch_adapter(flavor="retrodeck")
    assert isinstance(adapter, RetroDeckAdapter)

    adapter2 = get_retroarch_adapter(flavor=RetroArchFlavor.STANDALONE)
    assert isinstance(adapter2, StandaloneRetroArchAdapter)


def test_detector_configured_path_hints():
    """Verify configured path strings provide detection hints."""
    steam_path = "C:/Program Files (x86)/Steam/steamapps/common/RetroArch/retroarch.exe"
    adapter_steam = detect_retroarch_flavor(configured_path=steam_path)
    assert isinstance(adapter_steam, SteamRetroArchAdapter)

    retrodeck_path = "/home/deck/.var/app/net.retrodeck.retrodeck/data/retroarch"
    adapter_rd = detect_retroarch_flavor(configured_path=retrodeck_path)
    assert isinstance(adapter_rd, RetroDeckAdapter)


def test_detector_system_path_standalone(tmp_path):
    """Verify discovering standalone RetroArch on system PATH."""
    ra_bin = tmp_path / "retroarch"
    ra_bin.write_text("dummy")

    with patch("shutil.which", side_effect=lambda cmd: str(ra_bin) if cmd == "retroarch" else None):
        adapter = detect_retroarch_flavor(os_platform="linux", home_dir=tmp_path)
        assert isinstance(adapter, StandaloneRetroArchAdapter)


def test_detector_retrodeck_filesystem_presence(tmp_path):
    """Verify detecting RetroDECK on Linux based on .var/app directory."""
    rd_dir = tmp_path / ".var" / "app" / "net.retrodeck.retrodeck"
    rd_dir.mkdir(parents=True)

    with patch("shutil.which", return_value=None):
        adapter = detect_retroarch_flavor(os_platform="linux", home_dir=tmp_path)
        assert isinstance(adapter, RetroDeckAdapter)


def test_detector_default_fallback(tmp_path):
    """Verify default fallback to Standalone when no other cues match."""
    with patch("shutil.which", return_value=None), \
         patch("romm_steam_sync.adapters.retroarch.steam.SteamRetroArchAdapter.resolve_binary", return_value=None), \
         patch("romm_steam_sync.adapters.retroarch.standalone.StandaloneRetroArchAdapter.resolve_binary", return_value=None):
        adapter = detect_retroarch_flavor(os_platform="win32", home_dir=tmp_path)
        assert isinstance(adapter, StandaloneRetroArchAdapter)
