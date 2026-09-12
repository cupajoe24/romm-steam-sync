"""Unit tests for RetroArchConfigAdapter and retroarch.cfg parsing."""

from pathlib import Path
from unittest.mock import patch

from romm_steam_sync.adapters.retroarch_config import (
    RetroArchConfigAdapter,
    parse_core_info,
    parse_retroarch_cfg_line,
)


def test_parseRetroarchCfgLine_parsesStandardKeyValue():
    k, v = parse_retroarch_cfg_line('savefiles_in_content_dir = "true"')
    assert k == "savefiles_in_content_dir"
    assert v == "true"


def test_parseRetroarchCfgLine_parsesUnquotedValue():
    k, v = parse_retroarch_cfg_line("sort_savefiles_enable = false")
    assert k == "sort_savefiles_enable"
    assert v == "false"


def test_parseRetroarchCfgLine_ignoresCommentsAndBlankLines():
    assert parse_retroarch_cfg_line("# this is a comment") == ("", "")
    assert parse_retroarch_cfg_line("   ") == ("", "")
    assert parse_retroarch_cfg_line("invalid line without equals") == ("", "")


def test_parseCoreInfo_extractsKeyValues(tmp_path):
    info_text = """
# Software Information
display_name = "Nintendo - Game Boy Advance (mGBA)"
authors = "endrift"
corename = "mGBA"
supported_extensions = "gb|gbc|gba"
"""
    parsed = parse_core_info(info_text)
    assert parsed.get("corename") == "mGBA"
    assert parsed.get("display_name") == "Nintendo - Game Boy Advance (mGBA)"
    assert parsed.get("supported_extensions") == "gb|gbc|gba"


def test_resolveRetroarchCfgPath_findsFileAlongsideConfiguredBinary(tmp_path):
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    cfg_file = ra_dir / "retroarch.cfg"
    cfg_file.write_text('savefiles_in_content_dir = "false"\n', encoding="utf-8")
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.write_bytes(b"dummy")

    adapter = RetroArchConfigAdapter(configured_retroarch_path=str(ra_exe))
    found = adapter.resolve_retroarch_cfg_path()

    assert found == cfg_file


def test_getConfigSettings_parsesSettingsCorrectly(tmp_path):
    cfg_file = tmp_path / "retroarch.cfg"
    cfg_file.write_text(
        'savefiles_in_content_dir = "false"\n'
        'savefile_directory = ":\\saves"\n'
        'sort_savefiles_by_content_enable = "false"\n'
        'sort_savefiles_enable = "true"\n'
        'libretro_info_path = ":\\info"\n',
        encoding="utf-8",
    )

    adapter = RetroArchConfigAdapter(configured_retroarch_path=str(cfg_file))
    settings = adapter.get_config_settings()

    assert settings["savefiles_in_content_dir"] is False
    assert settings["savefile_directory"] == ":\\saves"
    assert settings["sort_savefiles_by_content_enable"] is False
    assert settings["sort_savefiles_enable"] is True
    assert settings["libretro_info_path"] == ":\\info"


def test_resolveSaveDirectory_contentDirMode(tmp_path):
    cfg_file = tmp_path / "retroarch.cfg"
    cfg_file.write_text('savefiles_in_content_dir = "true"\n', encoding="utf-8")

    rom_file = tmp_path / "roms" / "gba" / "Game.gba"
    rom_file.parent.mkdir(parents=True)
    rom_file.write_bytes(b"rom")

    adapter = RetroArchConfigAdapter(configured_retroarch_path=str(cfg_file))
    save_dir = adapter.resolve_save_directory(str(rom_file), "gba", "mgba_libretro")

    assert save_dir == rom_file.parent


def test_resolveSaveDirectory_sortSavesByCore(tmp_path):
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    cfg_file = ra_dir / "retroarch.cfg"
    cfg_file.write_text(
        'savefiles_in_content_dir = "false"\n'
        'savefile_directory = ":\\saves"\n'
        'sort_savefiles_enable = "true"\n'
        'sort_savefiles_by_content_enable = "false"\n',
        encoding="utf-8",
    )
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "roms" / "gba" / "Golden Sun.zip"
    rom_file.parent.mkdir(parents=True)
    rom_file.write_bytes(b"rom")

    adapter = RetroArchConfigAdapter(configured_retroarch_path=str(ra_exe))
    save_dir = adapter.resolve_save_directory(str(rom_file), "gba", "mgba_libretro")

    assert save_dir == (ra_dir / "saves" / "mGBA").resolve()


def test_resolveSaveDirectory_sortSavesByContentAndCore(tmp_path):
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    cfg_file = ra_dir / "retroarch.cfg"
    cfg_file.write_text(
        'savefiles_in_content_dir = "false"\n'
        'savefile_directory = ":\\saves"\n'
        'sort_savefiles_enable = "true"\n'
        'sort_savefiles_by_content_enable = "true"\n',
        encoding="utf-8",
    )
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "roms" / "snes" / "Super Mario World.sfc"
    rom_file.parent.mkdir(parents=True)
    rom_file.write_bytes(b"rom")

    adapter = RetroArchConfigAdapter(configured_retroarch_path=str(ra_exe))
    save_dir = adapter.resolve_save_directory(str(rom_file), "snes", "snes9x_libretro")

    assert save_dir == (ra_dir / "saves" / "snes" / "Snes9x").resolve()


def test_resolveCoreName_readsFromInfoFile(tmp_path):
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    info_dir = ra_dir / "info"
    info_dir.mkdir()
    info_file = info_dir / "customcore_libretro.info"
    info_file.write_text('corename = "MyCustomCore"\n', encoding="utf-8")
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.write_bytes(b"dummy")

    adapter = RetroArchConfigAdapter(configured_retroarch_path=str(ra_exe))
    core_name = adapter.resolve_core_name("customcore_libretro")

    assert core_name == "MyCustomCore"
