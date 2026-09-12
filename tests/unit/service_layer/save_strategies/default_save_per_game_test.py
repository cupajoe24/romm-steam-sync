"""Unit tests for DefaultSavePerGameStrategy and hash/quarantine utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import zipfile

from romm_steam_sync.service_layer.save_strategies.default_save_per_game import (
    DefaultSavePerGameStrategy,
    calculate_save_hash,
    find_local_save_file,
    quarantine_local_save,
)


def test_calculateSaveHash_singleFile_returnsHexDigest(tmp_path):
    # Arrange
    save_file = tmp_path / "game.srm"
    save_file.write_bytes(b"hello save data")

    # Act
    h = calculate_save_hash(str(save_file))

    # Assert
    assert isinstance(h, str)
    assert len(h) == 32


def test_calculateSaveHash_zipFile_computesDeterministicHash(tmp_path):
    # Arrange
    zip_path = tmp_path / "save.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("SaveCommon.bin", b"DATA_1")
        zf.writestr("Save_0.bin", b"DATA_2")

    # Act
    h = calculate_save_hash(str(zip_path))

    # Assert
    assert isinstance(h, str)
    assert len(h) == 32


def test_findLocalSaveFile_locatesSrmNextToRom(tmp_path):
    # Arrange
    rom_file = tmp_path / "Super Mario World.sfc"
    rom_file.write_bytes(b"rom")
    save_file = tmp_path / "Super Mario World.srm"
    save_file.write_bytes(b"save")

    # Act
    existing, target = find_local_save_file(str(rom_file))

    # Assert
    assert existing == save_file


def test_findLocalSaveFile_n64Eeprom_discoversAlternateExtensions(tmp_path):
    # Arrange
    rom_file = tmp_path / "Mario64.z64"
    rom_file.write_bytes(b"rom")
    eeprom_file = tmp_path / "Mario64.eep"
    eeprom_file.write_bytes(b"eeprom")

    # Act
    existing, target = find_local_save_file(str(rom_file))

    # Assert
    assert existing == eeprom_file


def test_quarantineLocalSave_movesFileToBackupDirectory(tmp_path):
    # Arrange
    save_file = tmp_path / "corrupted.srm"
    save_file.write_bytes(b"old corrupt save")

    # Act
    backup_file_str = quarantine_local_save(save_file)

    # Assert
    backup_path = Path(backup_file_str)
    assert not save_file.exists()
    assert backup_path.exists()
    assert ".romm-backup" in str(backup_path)
    assert backup_path.read_bytes() == b"old corrupt save"


def test_syncPreLaunch_downloadsRemoteSave(tmp_path):
    # Arrange
    strat = DefaultSavePerGameStrategy()
    rom_file = tmp_path / "Pokemon.gba"
    rom_file.write_bytes(b"rom")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = [
        {"id": 1, "name": "Pokemon.srm", "content_hash": "abc"}
    ]

    def fake_download(save_id, target_path):
        Path(target_path).write_bytes(b"downloaded save")
        return True

    mock_client.download_save_content.side_effect = fake_download

    # Act
    with patch(
        "romm_steam_sync.adapters.retroarch_config.RetroArchLauncher.resolve_retroarch_binary",
        return_value=None,
    ), patch(
        "romm_steam_sync.adapters.retroarch_config.RetroArchConfigAdapter.resolve_retroarch_cfg_path",
        return_value=None,
    ):
        action, msg, remote_save, target_path = strat.sync_pre_launch(
            rom_id=10,
            rom_path=str(rom_file),
            platform_slug="gba",
            client=mock_client,
        )

    # Assert
    assert action == "DOWNLOAD"
    assert target_path == tmp_path / "Pokemon.srm"
    assert target_path.exists()
    assert target_path.read_bytes() == b"downloaded save"


def test_syncPostLaunch_uploadsLocalSave(tmp_path):
    # Arrange
    strat = DefaultSavePerGameStrategy()
    save_file = tmp_path / "Pokemon.srm"
    save_file.write_bytes(b"new save data")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = []
    mock_client.upload_save.return_value = {"id": 2, "name": "Pokemon.srm"}

    # Act
    success, msg = strat.sync_post_launch(
        rom_id=10,
        save_path=str(save_file),
        client=mock_client,
    )

    # Assert
    assert success is True
    mock_client.upload_save.assert_called_once_with(10, str(save_file), save_id=None, slot="autosave")


def test_findLocalSaveFile_macOsApplicationSupportPath(tmp_path):
    # Arrange
    fake_home = tmp_path / "home"
    mac_saves = fake_home / "Library" / "Application Support" / "RetroArch" / "saves"
    mac_saves.mkdir(parents=True)
    fake_save = mac_saves / "Chrono Trigger.srm"
    fake_save.write_bytes(b"snes save data")

    rom_file = tmp_path / "roms" / "Chrono Trigger.sfc"
    rom_file.parent.mkdir(parents=True)
    rom_file.write_bytes(b"dummy sfc")

    with patch("romm_steam_sync.adapters.retroarch_config.sys.platform", "darwin"), \
         patch("romm_steam_sync.adapters.retroarch_config.Path.home", return_value=fake_home), \
         patch("romm_steam_sync.service_layer.save_strategies.default_save_per_game.sys.platform", "darwin"), \
         patch("romm_steam_sync.service_layer.save_strategies.default_save_per_game.Path.home", return_value=fake_home), \
         patch("romm_steam_sync.adapters.retroarch_config.RetroArchLauncher.resolve_retroarch_binary", return_value=None), \
         patch("romm_steam_sync.service_layer.save_strategies.default_save_per_game.RetroArchLauncher.resolve_retroarch_binary", return_value=None):
        # Act
        existing, target = find_local_save_file(str(rom_file), platform_slug="snes")

        # Assert
        assert existing == fake_save


def test_findLocalSaveFile_sortSavesByCore_targetsCoreFolder(tmp_path):
    # Arrange
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    cfg_file = ra_dir / "retroarch.cfg"
    cfg_file.write_text(
        'savefiles_in_content_dir = "false"\n'
        'savefile_directory = ":\\saves"\n'
        'sort_savefiles_enable = "true"\n',
        encoding="utf-8",
    )
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "roms" / "gba" / "Golden Sun.zip"
    rom_file.parent.mkdir(parents=True)
    rom_file.write_bytes(b"dummy zip")

    # Act
    existing, target = find_local_save_file(
        str(rom_file),
        platform_slug="gba",
        core_name="mgba_libretro",
        configured_retroarch_path=str(ra_exe),
    )

    # Assert
    assert existing is None
    expected_target = (ra_dir / "saves" / "mGBA" / "Golden Sun.srm").resolve()
    assert target == expected_target


def test_syncPreLaunch_migratesOrphanedSaveToRetroArchTarget(tmp_path):
    # Arrange
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    cfg_file = ra_dir / "retroarch.cfg"
    cfg_file.write_text(
        'savefiles_in_content_dir = "false"\n'
        'savefile_directory = ":\\saves"\n'
        'sort_savefiles_enable = "true"\n',
        encoding="utf-8",
    )
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.write_bytes(b"dummy")

    rom_dir = tmp_path / "roms" / "gba"
    rom_dir.mkdir(parents=True)
    rom_file = rom_dir / "Golden Sun.zip"
    rom_file.write_bytes(b"dummy zip")
    orphaned_save = rom_dir / "Golden Sun.srm"
    orphaned_save.write_bytes(b"original save data from rom directory")

    strat = DefaultSavePerGameStrategy()
    mock_client = MagicMock()
    mock_client.get_saves.return_value = []

    # Act
    action, msg, remote, target = strat.sync_pre_launch(
        rom_id=123,
        rom_path=str(rom_file),
        platform_slug="gba",
        client=mock_client,
        core_name="mgba_libretro",
        configured_retroarch_path=str(ra_exe),
    )

    # Assert
    expected_target = (ra_dir / "saves" / "mGBA" / "Golden Sun.srm").resolve()
    assert target == expected_target
    assert expected_target.exists()
    assert expected_target.read_bytes() == b"original save data from rom directory"


