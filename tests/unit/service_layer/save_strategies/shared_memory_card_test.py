"""Unit tests for SharedMemoryCardStrategy (PS2 / LRPS2 / PCSX2 and Flycast memory card swapping)."""

from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

from romm_steam_sync.service_layer.save_strategies.registry import get_save_strategy
from romm_steam_sync.service_layer.save_strategies.shared_memory_card import (
    SharedMemoryCardStrategy,
    get_app_local_memcard_path,
    get_memcard_system_folder,
    get_retroarch_memcard_path,
)


def test_getMemcardSystemFolder_forPs2_returnsPcsx2():
    # Arrange & Act & Assert
    assert get_memcard_system_folder("pcsx2_libretro") == "pcsx2"
    assert get_memcard_system_folder("lrps2_libretro") == "pcsx2"
    assert get_memcard_system_folder("lrps2") == "pcsx2"
    assert get_memcard_system_folder("pcsx2") == "pcsx2"
    assert get_memcard_system_folder("", platform_slug="ps2") == "pcsx2"
    assert get_memcard_system_folder("", platform_slug="playstation-2") == "pcsx2"
    assert get_memcard_system_folder("", platform_slug="playstation_2") == "pcsx2"
    assert get_memcard_system_folder("", platform_slug="playstation 2") == "pcsx2"
    assert get_memcard_system_folder("", platform_slug="sony-playstation-2") == "pcsx2"
    assert get_memcard_system_folder("", platform_slug="sony playstation 2") == "pcsx2"


def test_getAppLocalMemcardPath_constructsCanonicalPs2Path(tmp_path):
    # Arrange
    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=tmp_path):
        # Act
        card_path = get_app_local_memcard_path("lrps2_libretro", "Final Fantasy X", "Mcd001.ps2")

        # Assert
        expected = tmp_path / "memcards" / "pcsx2" / "Final Fantasy X" / "Mcd001.ps2"
        assert card_path == expected
        assert card_path.parent.exists()


def test_getSaveStrategy_resolvesPs2Cores():
    # Arrange & Act
    strat_pcsx2 = get_save_strategy(core_name="pcsx2_libretro")
    strat_lrps2 = get_save_strategy(core_name="lrps2_libretro.dll")
    strat_ps2_platform = get_save_strategy(platform_slug="ps2")
    strat_playstation2 = get_save_strategy(platform_slug="playstation-2")
    strat_sony_ps2 = get_save_strategy(platform_slug="sony-playstation-2")

    # Assert
    assert strat_pcsx2.name == "shared_memory_card"
    assert strat_lrps2.name == "shared_memory_card"
    assert strat_ps2_platform.name == "shared_memory_card"
    assert strat_playstation2.name == "shared_memory_card"
    assert strat_sony_ps2.name == "shared_memory_card"


def test_resolveCardFilename_standardizesPs2Names():
    # Arrange
    strat = SharedMemoryCardStrategy()

    # Act & Assert
    assert strat.resolve_card_filename(platform_slug="playstation-2") == "Mcd001.ps2"
    assert strat.resolve_card_filename(core_name="pcsx2_libretro") == "Mcd001.ps2"

    # Any remote save name (including game names, lowercase, or slot 2) resolves strictly to Mcd001.ps2 for PS2
    remote_save_game = {"id": 10, "name": "Amplitude (USA).ps2", "file_name": "Amplitude (USA).ps2"}
    assert strat.resolve_card_filename(remote_save_game, platform_slug="playstation-2") == "Mcd001.ps2"

    remote_save_lower = {"id": 11, "name": "mcd001.ps2", "file_name": "mcd001.ps2"}
    assert strat.resolve_card_filename(remote_save_lower, platform_slug="playstation-2") == "Mcd001.ps2"

    remote_save_slot2 = {"id": 12, "name": "Mcd002.ps2", "file_name": "Mcd002.ps2"}
    assert strat.resolve_card_filename(remote_save_slot2, platform_slug="playstation-2") == "Mcd001.ps2"

    remote_save_mcd = {"id": 13, "name": "Final Fantasy X.mcd", "file_name": "Final Fantasy X.mcd"}
    assert strat.resolve_card_filename(remote_save_mcd, platform_slug="ps2") == "Mcd001.ps2"


def test_consolidateLocalMemcards_renamesCustomSaveToStandardName(tmp_path):
    # Arrange
    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=tmp_path):
        game_dir = tmp_path / "memcards" / "pcsx2" / "Amplitude (USA)"
        game_dir.mkdir(parents=True, exist_ok=True)
        non_standard_card = game_dir / "Amplitude (USA).ps2"
        non_standard_card.write_bytes(b"amplitude save data")

        # Act
        card_path = get_app_local_memcard_path("lrps2_libretro", "Amplitude (USA)", "Mcd001.ps2")

        # Assert
        assert card_path.name == "Mcd001.ps2"
        assert card_path.exists()
        assert card_path.read_bytes() == b"amplitude save data"
        assert not non_standard_card.exists()


def test_consolidateLocalMemcards_handlesCaseOnlyRename(tmp_path):
    # Arrange
    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=tmp_path):
        game_dir = tmp_path / "memcards" / "pcsx2" / "Amplitude (USA)"
        game_dir.mkdir(parents=True, exist_ok=True)
        lower_card = game_dir / "mcd001.ps2"
        lower_card.write_bytes(b"lowercase memcard data")

        # Act
        card_path = get_app_local_memcard_path("lrps2_libretro", "Amplitude (USA)", "Mcd001.ps2")

        # Assert
        assert card_path.name == "Mcd001.ps2"
        assert card_path.exists()
        assert card_path.read_bytes() == b"lowercase memcard data"


def test_getAppLocalMemcardPath_migratesLegacyPlaystation2Folder(tmp_path):
    # Arrange
    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=tmp_path):
        legacy_dir = tmp_path / "memcards" / "playstation-2" / "Gran Turismo 4"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        legacy_card = legacy_dir / "Mcd001.ps2"
        legacy_card.write_bytes(b"legacy save data")

        # Act
        card_path = get_app_local_memcard_path("", "Gran Turismo 4", "Mcd001.ps2", platform_slug="playstation-2")

        # Assert
        assert card_path == tmp_path / "memcards" / "pcsx2" / "Gran Turismo 4" / "Mcd001.ps2"
        assert card_path.exists()
        assert card_path.read_bytes() == b"legacy save data"


def test_syncPreLaunch_downloadsAndSwapsPlaystation2Slug(tmp_path):
    # Arrange
    app_config_dir = tmp_path / "app_data"
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")
    (ra_dir / "system").mkdir(parents=True, exist_ok=True)

    rom_file = tmp_path / "Games" / "Amplitude (USA).iso"
    rom_file.parent.mkdir(parents=True, exist_ok=True)
    rom_file.write_bytes(b"dummy iso")

    ra_memcard = ra_dir / "system" / "pcsx2" / "memcards" / "Mcd001.ps2"

    mock_client = MagicMock()
    # Remote save has game-specific non-standard filename
    mock_client.get_saves.return_value = [{"id": 42, "name": "Amplitude (USA).ps2", "content_hash": "remote_hash"}]

    def fake_download(save_id, target_path):
        Path(target_path).write_bytes(b"downloaded amplitude save")
        return True

    mock_client.download_save_content.side_effect = fake_download
    strat = SharedMemoryCardStrategy()

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=app_config_dir), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):

        # Act: launched with empty core_name and platform_slug="playstation-2"
        action, msg, remote_save, target_card = strat.sync_pre_launch(
            rom_id=42,
            rom_path=str(rom_file),
            platform_slug="playstation-2",
            client=mock_client,
            configured_retroarch_path=str(ra_exe),
            core_name="",
        )

    # Assert: Staged strictly to pcsx2/memcards/Mcd001.ps2
    assert action == "DOWNLOAD"
    assert target_card == ra_memcard
    assert ra_memcard.exists()
    assert ra_memcard.read_bytes() == b"downloaded amplitude save"
    local_app_card = app_config_dir / "memcards" / "pcsx2" / "Amplitude (USA)" / "Mcd001.ps2"
    assert local_app_card.exists()
    assert local_app_card.read_bytes() == b"downloaded amplitude save"


def test_getRetroarchMemcardPath_avoidsProgramFiles(tmp_path):
    # Arrange
    prog_files_exe = r"C:\Program Files\RetroArch-Win64\retroarch.exe"
    appdata_dir = tmp_path / "AppData" / "Roaming" / "RetroArch" / "system"
    appdata_dir.mkdir(parents=True, exist_ok=True)

    with patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=prog_files_exe), \
         patch("sys.platform", "win32"), \
         patch("pathlib.Path.home", return_value=tmp_path):

        # Act
        resolved = get_retroarch_memcard_path(prog_files_exe, platform_slug="playstation-2")

        # Assert: resolves under user's AppData, NOT Program Files
        assert "Program Files" not in str(resolved)
        assert resolved == appdata_dir / "pcsx2" / "memcards" / "Mcd001.ps2"


def test_syncPreLaunch_downloadsAndSwapsPs2Card(tmp_path):
    # Arrange
    app_config_dir = tmp_path / "app_data"
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "Games" / "Final Fantasy X.iso"
    rom_file.parent.mkdir(parents=True, exist_ok=True)
    rom_file.write_bytes(b"dummy iso")

    ra_memcard = ra_dir / "system" / "pcsx2" / "memcards" / "Mcd001.ps2"
    ra_memcard.parent.mkdir(parents=True, exist_ok=True)
    ra_memcard.write_bytes(b"stale retroarch card")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = [{"id": 99, "name": "Mcd001.ps2", "content_hash": "remote_hash"}]

    def fake_download(save_id, target_path):
        Path(target_path).write_bytes(b"fresh remote memory card data")
        return True

    mock_client.download_save_content.side_effect = fake_download
    strat = SharedMemoryCardStrategy()

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=app_config_dir), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):

        # Act
        action, msg, remote_save, target_card = strat.sync_pre_launch(
            rom_id=50,
            rom_path=str(rom_file),
            platform_slug="ps2",
            client=mock_client,
            configured_retroarch_path=str(ra_exe),
        )

    # Assert
    assert action == "DOWNLOAD"
    local_app_card = app_config_dir / "memcards" / "pcsx2" / "Final Fantasy X" / "Mcd001.ps2"
    assert local_app_card.exists()
    assert local_app_card.read_bytes() == b"fresh remote memory card data"
    assert ra_memcard.exists()
    assert ra_memcard.read_bytes() == b"fresh remote memory card data"


def test_syncPreLaunch_offlineFallback_copiesLocalCard(tmp_path):
    # Arrange
    app_config_dir = tmp_path / "app_data"
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / ("retroarch.exe" if sys.platform == "win32" else "retroarch")
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")
    (ra_dir / "system").mkdir(parents=True, exist_ok=True)

    rom_file = tmp_path / "Games" / "Kingdom Hearts.iso"
    rom_file.parent.mkdir(parents=True, exist_ok=True)
    rom_file.write_bytes(b"dummy iso")

    local_app_card = app_config_dir / "memcards" / "pcsx2" / "Kingdom Hearts" / "Mcd001.ps2"
    local_app_card.parent.mkdir(parents=True, exist_ok=True)
    local_app_card.write_bytes(b"offline local app card data")

    ra_memcard = ra_dir / "system" / "pcsx2" / "memcards" / "Mcd001.ps2"
    mock_client = MagicMock()
    mock_client.get_saves.side_effect = Exception("RomM Server Offline")
    strat = SharedMemoryCardStrategy()

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=app_config_dir), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):

        # Act
        action, msg, remote_save, target_card = strat.sync_pre_launch(
            rom_id=51,
            rom_path=str(rom_file),
            platform_slug="ps2",
            client=mock_client,
            configured_retroarch_path=str(ra_exe),
        )

    # Assert
    assert action == "UPLOAD" or action == "NO_OP" or "Offline" in msg
    assert ra_memcard.exists()
    assert ra_memcard.read_bytes() == b"offline local app card data"


def test_syncPostLaunch_updatesLocalAndUploads(tmp_path):
    # Arrange
    app_config_dir = tmp_path / "app_data"
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "Games" / "Final Fantasy X.iso"
    ra_memcard = ra_dir / "system" / "pcsx2" / "memcards" / "Mcd001.ps2"
    ra_memcard.parent.mkdir(parents=True, exist_ok=True)
    ra_memcard.write_bytes(b"new in-game save data from playing")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = [{"id": 99, "name": "Mcd001.ps2"}]
    strat = SharedMemoryCardStrategy()

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=app_config_dir), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):

        # Act
        success, msg = strat.sync_post_launch(
            rom_id=50,
            save_path=str(rom_file),
            client=mock_client,
            platform_slug="ps2",
            configured_retroarch_path=str(ra_exe),
        )

    # Assert
    assert success is True
    local_app_card = app_config_dir / "memcards" / "pcsx2" / "Final Fantasy X" / "Mcd001.ps2"
    assert local_app_card.exists()
    assert local_app_card.read_bytes() == b"new in-game save data from playing"
    mock_client.upload_save.assert_called_once_with(50, str(local_app_card), save_id=99, slot="autosave")
    assert not ra_memcard.exists()


def test_syncPreLaunch_whenNoSavesAnywhere_handlesCleanly(tmp_path):
    # Arrange
    app_config_dir = tmp_path / "app_data"
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "Games" / "Brand New Game.iso"
    rom_file.parent.mkdir(parents=True, exist_ok=True)
    rom_file.write_bytes(b"dummy iso")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = []
    strat = SharedMemoryCardStrategy()

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=app_config_dir), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):

        # Act
        action, msg, remote_save, target_card = strat.sync_pre_launch(
            rom_id=52,
            rom_path=str(rom_file),
            platform_slug="ps2",
            client=mock_client,
            configured_retroarch_path=str(ra_exe),
        )

    # Assert
    assert action == "NO_OP"
    assert remote_save is None
    assert not mock_client.download_save_content.called
    assert not mock_client.upload_save.called

    # When game exits after creating a save in RetroArch for the first time:
    ra_memcard = ra_dir / "system" / "pcsx2" / "memcards" / "Mcd001.ps2"
    ra_memcard.parent.mkdir(parents=True, exist_ok=True)
    ra_memcard.write_bytes(b"first in-game save data")

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=app_config_dir), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):
        success, post_msg = strat.sync_post_launch(
            rom_id=52,
            save_path=str(rom_file),
            client=mock_client,
            platform_slug="ps2",
            configured_retroarch_path=str(ra_exe),
        )

    assert success is True
    local_app_card = app_config_dir / "memcards" / "pcsx2" / "Brand New Game" / "Mcd001.ps2"
    assert local_app_card.exists()
    assert local_app_card.read_bytes() == b"first in-game save data"
    mock_client.upload_save.assert_called_once_with(52, str(local_app_card), save_id=None, slot="autosave")
    assert not ra_memcard.exists()


def test_getMemcardSystemFolder_forFlycast_returnsDc():
    # Arrange & Act & Assert
    assert get_memcard_system_folder("flycast_libretro") == "dc"
    assert get_memcard_system_folder("flycast") == "dc"
    assert get_memcard_system_folder("flycast_gles2_libretro") == "dc"
    assert get_memcard_system_folder("reicast_libretro") == "dc"
    assert get_memcard_system_folder("", platform_slug="dc") == "dc"
    assert get_memcard_system_folder("", platform_slug="dreamcast") == "dc"
    assert get_memcard_system_folder("", platform_slug="sega-dreamcast") == "dc"
    assert get_memcard_system_folder("", platform_slug="naomi") == "dc"
    assert get_memcard_system_folder("", platform_slug="atomiswave") == "dc"


def test_getAppLocalMemcardPath_constructsCanonicalFlycastPath(tmp_path):
    # Arrange
    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=tmp_path):
        # Act
        card_path = get_app_local_memcard_path("flycast_libretro", "Sonic Adventure", "vmu_save_A1.bin", "dreamcast")

        # Assert
        expected = tmp_path / "memcards" / "dc" / "Sonic Adventure" / "vmu_save_A1.bin"
        assert card_path == expected
        assert card_path.parent.exists()


def test_getRetroarchMemcardPath_resolvesFlycastSystemPath(tmp_path):
    # Arrange
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / ("retroarch.exe" if sys.platform == "win32" else "retroarch")
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")
    (ra_dir / "system").mkdir(parents=True, exist_ok=True)

    with patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):
        # Act
        ra_card = get_retroarch_memcard_path(str(ra_exe), core_name="flycast_libretro", platform_slug="dreamcast", card_filename="vmu_save_A1.bin")

        # Assert
        expected = ra_dir / "system" / "dc" / "vmu_save_A1.bin"
        assert ra_card == expected
        assert ra_card.parent.exists()


def test_getSaveStrategy_resolvesFlycastCores():
    # Arrange & Act
    strat_flycast = get_save_strategy(core_name="flycast_libretro")
    strat_dc_platform = get_save_strategy(platform_slug="dreamcast")
    strat_naomi = get_save_strategy(platform_slug="naomi")
    strat_atomiswave = get_save_strategy(platform_slug="atomiswave")

    # Assert
    assert strat_flycast.name == "shared_memory_card"
    assert strat_dc_platform.name == "shared_memory_card"
    assert strat_naomi.name == "shared_memory_card"
    assert strat_atomiswave.name == "shared_memory_card"


def test_resolveCardFilename_standardizesFlycastVmu():
    # Arrange
    strat = SharedMemoryCardStrategy()

    # Act & Assert
    assert strat.resolve_card_filename(platform_slug="dreamcast") == "vmu_save_A1.bin"
    assert strat.resolve_card_filename(core_name="flycast_libretro") == "vmu_save_A1.bin"
    remote_save = {"id": 12, "name": "Crazy Taxi (USA).bin", "file_name": "Crazy Taxi (USA).bin"}
    assert strat.resolve_card_filename(remote_save, platform_slug="dreamcast") == "vmu_save_A1.bin"
    remote_save_slot2 = {"id": 13, "name": "vmu_save_A2.bin", "file_name": "vmu_save_A2.bin"}
    assert strat.resolve_card_filename(remote_save_slot2, platform_slug="dreamcast") == "vmu_save_A2.bin"


def test_consolidateLocalMemcards_renamesCustomVmuToStandardName(tmp_path):
    # Arrange
    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=tmp_path):
        game_dir = tmp_path / "memcards" / "dc" / "Sonic Adventure"
        game_dir.mkdir(parents=True, exist_ok=True)
        non_standard_vmu = game_dir / "Sonic Adventure (USA).bin"
        non_standard_vmu.write_bytes(b"sonic adventure vmu data")

        # Act
        card_path = get_app_local_memcard_path("flycast_libretro", "Sonic Adventure", "vmu_save_A1.bin", "dreamcast")

        # Assert
        assert card_path.name == "vmu_save_A1.bin"
        assert card_path.exists()
        assert card_path.read_bytes() == b"sonic adventure vmu data"
        assert not non_standard_vmu.exists()


def test_syncPreLaunch_downloadsAndSwapsFlycastVmu(tmp_path):
    # Arrange
    app_config_dir = tmp_path / "app_data"
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / ("retroarch.exe" if sys.platform == "win32" else "retroarch")
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")
    (ra_dir / "system").mkdir(parents=True, exist_ok=True)

    rom_file = tmp_path / "Games" / "Sonic Adventure.gdi"
    rom_file.parent.mkdir(parents=True, exist_ok=True)
    rom_file.write_bytes(b"dummy gdi")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = [{"id": 77, "name": "vmu_save_A1.bin", "content_hash": "remote_vmu_hash"}]

    def fake_download(save_id, target_path):
        Path(target_path).write_bytes(b"fresh remote vmu data")
        return True

    mock_client.download_save_content.side_effect = fake_download
    strat = SharedMemoryCardStrategy()

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=app_config_dir), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):

        # Act
        action, msg, remote_save, target_card = strat.sync_pre_launch(
            rom_id=70,
            rom_path=str(rom_file),
            platform_slug="dreamcast",
            client=mock_client,
            configured_retroarch_path=str(ra_exe),
            core_name="flycast_libretro",
        )

    # Assert
    assert action == "DOWNLOAD"
    local_app_card = app_config_dir / "memcards" / "dc" / "Sonic Adventure" / "vmu_save_A1.bin"
    assert local_app_card.exists()
    assert local_app_card.read_bytes() == b"fresh remote vmu data"
    ra_vmu = ra_dir / "system" / "dc" / "vmu_save_A1.bin"
    assert ra_vmu.exists()
    assert ra_vmu.read_bytes() == b"fresh remote vmu data"


def test_syncPostLaunch_cleansUpVmuWithoutAffectingBios(tmp_path):
    # Arrange
    app_config_dir = tmp_path / "app_data"
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")

    dc_sys_dir = ra_dir / "system" / "dc"
    dc_sys_dir.mkdir(parents=True, exist_ok=True)
    dc_boot = dc_sys_dir / "dc_boot.bin"
    dc_boot.write_bytes(b"dreamcast bios boot rom")
    dc_flash = dc_sys_dir / "dc_flash.bin"
    dc_flash.write_bytes(b"dreamcast bios flash nvram")
    ra_vmu = dc_sys_dir / "vmu_save_A1.bin"
    ra_vmu.write_bytes(b"sonic adventure gameplay save")

    rom_file = tmp_path / "Games" / "Sonic Adventure.gdi"
    mock_client = MagicMock()
    mock_client.get_saves.return_value = [{"id": 77, "name": "vmu_save_A1.bin"}]
    strat = SharedMemoryCardStrategy()

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=app_config_dir), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):

        # Act
        success, msg = strat.sync_post_launch(
            rom_id=70,
            save_path=str(rom_file),
            client=mock_client,
            platform_slug="dreamcast",
            configured_retroarch_path=str(ra_exe),
            core_name="flycast_libretro",
        )

    # Assert
    assert success is True
    local_app_card = app_config_dir / "memcards" / "dc" / "Sonic Adventure" / "vmu_save_A1.bin"
    assert local_app_card.exists()
    assert local_app_card.read_bytes() == b"sonic adventure gameplay save"
    mock_client.upload_save.assert_called_once_with(70, str(local_app_card), save_id=77, slot="autosave")
    assert not ra_vmu.exists()
    assert dc_boot.exists()
    assert dc_boot.read_bytes() == b"dreamcast bios boot rom"
    assert dc_flash.exists()
    assert dc_flash.read_bytes() == b"dreamcast bios flash nvram"


def test_getRetroarchMemcardPath_linuxSystemBinary_avoidsUsrBinSystem(tmp_path):
    # Arrange
    fake_home = tmp_path / "home"
    usr_bin_ra = tmp_path / "usr" / "bin" / "retroarch"
    usr_bin_ra.parent.mkdir(parents=True)
    usr_bin_ra.touch()

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.sys.platform", "linux"), \
         patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.Path.home", return_value=fake_home), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(usr_bin_ra)):
        # Act
        card_path = get_retroarch_memcard_path(str(usr_bin_ra), core_name="pcsx2_libretro", platform_slug="ps2")

        # Assert: should NOT be under usr/bin/system, but rather under user's .config
        assert "usr" not in card_path.parts
        assert card_path.parts[:len(fake_home.parts)] == fake_home.parts
        assert card_path.name == "Mcd001.ps2"


def test_getRetroarchMemcardPath_macOsApplicationSupport(tmp_path):
    # Arrange
    fake_home = tmp_path / "home"

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.sys.platform", "darwin"), \
         patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.Path.home", return_value=fake_home), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=None):
        # Act
        card_path = get_retroarch_memcard_path(core_name="flycast_libretro", platform_slug="dreamcast")

        # Assert
        expected = fake_home / "Library" / "Application Support" / "RetroArch" / "system" / "dc" / "vmu_save_A1.bin"
        assert card_path == expected


def test_syncPreLaunch_whenLocalAndRemoteSaveDiffer_returnsConflictWithoutClobbering(tmp_path):
    # Arrange
    app_config_dir = tmp_path / "app_data"
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "Games" / "Shadow of the Colossus.iso"
    rom_file.parent.mkdir(parents=True, exist_ok=True)
    rom_file.write_bytes(b"dummy iso")

    # Local app memory card created during offline play
    local_app_card = app_config_dir / "memcards" / "pcsx2" / "Shadow of the Colossus" / "Mcd001.ps2"
    local_app_card.parent.mkdir(parents=True, exist_ok=True)
    local_app_card.write_bytes(b"offline local save data")

    # Runtime RetroArch memcard folder also contains the active card
    ra_memcard = ra_dir / "system" / "pcsx2" / "memcards" / "Mcd001.ps2"
    ra_memcard.parent.mkdir(parents=True, exist_ok=True)
    ra_memcard.write_bytes(b"offline local save data")

    mock_client = MagicMock()
    # Remote RomM save with different content and no common baseline
    mock_client.get_saves.return_value = [{"id": 105, "name": "Mcd001.ps2", "content_hash": "different_remote_hash"}]

    strat = SharedMemoryCardStrategy()

    with patch("romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir", return_value=app_config_dir), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)):

        # Act
        action, msg, remote_save, target_card = strat.sync_pre_launch(
            rom_id=105,
            rom_path=str(rom_file),
            platform_slug="ps2",
            client=mock_client,
            configured_retroarch_path=str(ra_exe),
        )

    # Assert: Must trigger CONFLICT and preserve local save without clobbering or downloading
    assert action == "CONFLICT"
    assert "conflict" in msg.lower()
    assert remote_save == {"id": 105, "name": "Mcd001.ps2", "content_hash": "different_remote_hash"}
    assert local_app_card.exists()
    assert local_app_card.read_bytes() == b"offline local save data"
    assert ra_memcard.exists()
    assert ra_memcard.read_bytes() == b"offline local save data"
    assert not mock_client.download_save_content.called


