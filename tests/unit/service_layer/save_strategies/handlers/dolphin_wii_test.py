"""Unit tests for Dolphin Nintendo Wii save strategy handler."""

from pathlib import Path
import struct
from unittest.mock import MagicMock, patch
import zipfile
import zlib

from romm_steam_sync.service_layer.save_strategies.handlers.dolphin_wii import (
    _WII_MAGIC,
    DolphinWiiHandler,
    consolidate_wii_save_directory,
    read_wii_disc_header,
    unpack_wii_save_archive,
)
from romm_steam_sync.service_layer.save_strategies.memory_card_per_game import (
    MemoryCardPerGameStrategy,
    get_handler,
)
from romm_steam_sync.service_layer.save_strategies.registry import (
    CORE_SAVE_STRATEGY_MAP,
    get_save_strategy,
)


def _create_dummy_wii_disc(
    path: Path,
    game_code: str = "RMCE",
    maker_code: str = "01",
    title: str = "Mario Kart Wii",
) -> Path:
    """Helper to construct a mock Wii disc header (0x60 bytes)."""
    header = bytearray(0x60)
    header[0:4] = game_code.encode("latin1")
    header[4:6] = maker_code.encode("latin1")
    header[0x18:0x1C] = _WII_MAGIC
    title_bytes = title.encode("latin1")
    header[0x20 : 0x20 + len(title_bytes)] = title_bytes
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)
    return path


def test_extractRomMetadata_fromIso_identifiesHeader(tmp_path):
    # Arrange
    handler = DolphinWiiHandler()
    rom_file = tmp_path / "Mario Kart Wii (USA).iso"
    _create_dummy_wii_disc(rom_file, game_code="RMCE", maker_code="01", title="Mario Kart Wii")

    # Act
    meta = handler.extract_rom_metadata(str(rom_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["game_code"] == "RMCE"
    assert meta["maker_code"] == "01"
    assert meta["title_id_low"] == "524d4345"
    assert meta["title_id"] == "00010000524D4345"
    assert meta["region"] == "USA"
    assert meta["title"] == "Mario Kart Wii"


def test_extractRomMetadata_fromRvz_identifiesHeader(tmp_path):
    # Arrange
    handler = DolphinWiiHandler()
    rvz_file = tmp_path / "Super Smash Bros. Brawl.rvz"
    prefix = b"RVZ\x01" + b"\x00" * (0x48 - 4)
    wii_header = bytearray(0x60)
    wii_header[0:4] = b"RSBE"
    wii_header[4:6] = b"01"
    wii_header[0x18:0x1C] = _WII_MAGIC
    title_bytes = b"Super Smash Bros Brawl"
    wii_header[0x20 : 0x20 + len(title_bytes)] = title_bytes
    rvz_file.write_bytes(prefix + wii_header)

    # Act
    meta = handler.extract_rom_metadata(str(rvz_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["game_code"] == "RSBE"
    assert meta["title_id_low"] == "52534245".lower()
    assert meta["title_id"] == "0001000052534245"
    assert meta["region"] == "USA"
    assert meta["title"] == "Super Smash Bros Brawl"


def test_extractRomMetadata_fromWbfs_identifiesHeader(tmp_path):
    # Arrange
    handler = DolphinWiiHandler()
    wbfs_file = tmp_path / "Donkey Kong Country Returns.wbfs"
    wbfs_data = bytearray(0x200)
    wbfs_data[0:4] = b"WBFS"

    disc_header = bytearray(0x60)
    disc_header[0:4] = b"SF8E"
    disc_header[4:6] = b"01"
    disc_header[0x18:0x1C] = _WII_MAGIC
    title_bytes = b"Donkey Kong Country Returns"
    disc_header[0x20 : 0x20 + len(title_bytes)] = title_bytes
    wbfs_data[0x100 : 0x100 + 0x60] = disc_header
    wbfs_file.write_bytes(wbfs_data)

    # Act
    meta = handler.extract_rom_metadata(str(wbfs_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["game_code"] == "SF8E"
    assert meta["title_id_low"] == "53463845".lower()
    assert meta["title"] == "Donkey Kong Country Returns"


def test_extractRomMetadata_fromCiso_identifiesHeader(tmp_path):
    # Arrange
    handler = DolphinWiiHandler()
    ciso_file = tmp_path / "Wii Sports Resort.ciso"
    raw_iso = bytearray(0x60)
    raw_iso[0:4] = b"RZTE"
    raw_iso[4:6] = b"01"
    raw_iso[0x18:0x1C] = _WII_MAGIC
    raw_iso[0x20 : 0x20 + 17] = b"Wii Sports Resort"

    ciso_data = bytearray(0x8060)
    ciso_data[0:4] = b"CISO"
    struct.pack_into("<I", ciso_data, 4, 0x8000)
    ciso_data[0x8000:0x8060] = raw_iso
    ciso_file.write_bytes(ciso_data)

    # Act
    meta = handler.extract_rom_metadata(str(ciso_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["game_code"] == "RZTE"
    assert meta["title_id_low"] == "525a5445"
    assert meta["title"] == "Wii Sports Resort"


def test_extractRomMetadata_fallbackFilenameTag(tmp_path):
    # Arrange
    handler = DolphinWiiHandler()
    rom_file = tmp_path / "Super Mario Galaxy [RMGE01].wbfs"
    rom_file.write_bytes(b"\x00" * 64)

    # Act
    meta = handler.extract_rom_metadata(str(rom_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["game_code"] == "RMGE"
    assert meta["maker_code"] == "01"
    assert meta["title_id_low"] == "524d4745"
    assert meta["region"] == "USA"


def test_extractRomMetadata_regionMappings(tmp_path):
    # Arrange
    handler = DolphinWiiHandler()
    eur_rom = _create_dummy_wii_disc(tmp_path / "EUR.iso", game_code="RMCP", title="MKWii EUR")
    jap_rom = _create_dummy_wii_disc(tmp_path / "JAP.iso", game_code="RMCJ", title="MKWii JAP")
    kor_rom = _create_dummy_wii_disc(tmp_path / "KOR.iso", game_code="RMCK", title="MKWii KOR")

    # Act & Assert
    assert handler.extract_rom_metadata(str(eur_rom))["region"] == "EUR"
    assert handler.extract_rom_metadata(str(jap_rom))["region"] == "JAP"
    assert handler.extract_rom_metadata(str(kor_rom))["region"] == "KOR"


def test_getSaveDirectories_returnsWiiNandPaths(tmp_path):
    # Arrange
    handler = DolphinWiiHandler()
    fake_ra = tmp_path / "RetroArch" / "retroarch.exe"
    fake_ra.parent.mkdir(parents=True, exist_ok=True)
    fake_ra.write_text("")

    with patch(
        "romm_steam_sync.service_layer.save_strategies.handlers.dolphin_wii.RetroArchLauncher.resolve_retroarch_binary",
        return_value=str(fake_ra),
    ):
        # Act
        dirs = handler.get_save_directories(
            configured_retroarch_path=str(fake_ra),
            rom_path="C:/Games/Mario Kart Wii.iso",
        )

        # Assert
        assert any("00010000" in str(d) and "Wii" in str(d) for d in dirs)


def test_resolveTargetSavePath_constructsWiiZipPath(tmp_path):
    # Arrange
    handler = DolphinWiiHandler()
    rom_file = tmp_path / "Mario Kart Wii.iso"
    _create_dummy_wii_disc(rom_file, game_code="RMCE")
    base_nand = tmp_path / "saves" / "dolphin-emu" / "User" / "Wii" / "title" / "00010000"

    # Act
    target = handler.resolve_target_save_path([base_nand], str(rom_file))

    # Assert
    expected = base_nand / "524d4345" / "data" / "524d4345.zip"
    assert target == expected


def test_findExistingSave_withDataFiles_consolidatesIntoZip(tmp_path):
    # Arrange
    handler = DolphinWiiHandler()
    rom_file = tmp_path / "Mario Kart Wii.iso"
    _create_dummy_wii_disc(rom_file, game_code="RMCE")
    base_nand = tmp_path / "saves" / "dolphin-emu" / "User" / "Wii" / "title" / "00010000"
    data_dir = base_nand / "524d4345" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "banner.bin").write_bytes(b"WII_BANNER_DATA")
    (data_dir / "save.dat").write_bytes(b"WII_GAME_SAVE_DATA")

    # Act
    found = handler.find_existing_save([base_nand], str(rom_file))

    # Assert
    assert found is not None
    assert found.suffix == ".zip"
    assert found.exists()
    with zipfile.ZipFile(found, "r") as zf:
        assert sorted(zf.namelist()) == ["banner.bin", "save.dat"]


def test_syncPreLaunch_downloadsAndUnpacksWiiZip(tmp_path):
    # Arrange
    strategy = MemoryCardPerGameStrategy()
    rom_file = tmp_path / "roms" / "wii" / "Mario Kart Wii.iso"
    _create_dummy_wii_disc(rom_file, game_code="RMCE")
    saves_dir = tmp_path / "saves" / "dolphin-emu" / "User" / "Wii" / "title" / "00010000"

    mock_client = MagicMock()
    mock_client.get_saves.return_value = [
        {
            "id": 88,
            "name": "524d4345.zip",
            "file_name": "524d4345.zip",
            "content_hash": "wiihash123",
            "updated_at": "2026-08-30T12:00:00Z",
        }
    ]

    def _fake_download(save_id, dest):
        dest_p = Path(dest)
        dest_p.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest_p, "w") as zf:
            zf.writestr("banner.bin", b"DOWNLOADED_WII_BANNER")
            zf.writestr("save.dat", b"DOWNLOADED_WII_SAVE")
        return True

    mock_client.download_save_content.side_effect = _fake_download

    with patch.object(
        DolphinWiiHandler,
        "get_save_directories",
        return_value=[saves_dir],
    ):
        # Act
        action, msg, remote_save, target_path = strategy.sync_pre_launch(
            rom_id=202,
            rom_path=str(rom_file),
            platform_slug="wii",
            client=mock_client,
            core_name="dolphin_libretro",
        )

    # Assert
    assert action == "DOWNLOAD"
    assert target_path.exists()
    dest_data_dir = target_path.parent / "data"
    assert (dest_data_dir / "banner.bin").exists()
    assert (dest_data_dir / "save.dat").read_bytes() == b"DOWNLOADED_WII_SAVE"


def test_syncPostLaunch_archivesAndUploadsWiiSave(tmp_path):
    # Arrange
    strategy = MemoryCardPerGameStrategy()
    rom_file = tmp_path / "Mario Kart Wii.iso"
    _create_dummy_wii_disc(rom_file, game_code="RMCE")
    saves_dir = tmp_path / "saves" / "dolphin-emu" / "User" / "Wii" / "title" / "00010000"
    data_dir = saves_dir / "524d4345" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "banner.bin").write_bytes(b"UPDATED_WII_BANNER")
    (data_dir / "save.dat").write_bytes(b"UPDATED_WII_SAVE")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = []
    mock_client.upload_save.return_value = {"id": 202, "content_hash": "xyz"}

    with patch.object(
        DolphinWiiHandler,
        "get_save_directories",
        return_value=[saves_dir],
    ):
        # Act
        success, msg = strategy.sync_post_launch(
            rom_id=202,
            save_path=str(rom_file),
            client=mock_client,
            slot="autosave",
            platform_slug="wii",
            rom_path=str(rom_file),
            core_name="dolphin_libretro",
        )

    # Assert
    assert success is True
    expected_zip = data_dir.parent / "524d4345.zip"
    mock_client.upload_save.assert_called_once_with(
        202, str(expected_zip), save_id=None, slot="autosave"
    )


def test_getHandler_routesWiiPlatformToDolphinWiiHandler():
    # Arrange & Act
    handler_wii = get_handler("dolphin_libretro", "wii")
    handler_wii_slug = get_handler("", "nintendo-wii")
    handler_gc = get_handler("dolphin_libretro", "gc")
    handler_gc_slug = get_handler("", "nintendo-gamecube")

    # Assert
    assert isinstance(handler_wii, DolphinWiiHandler)
    assert isinstance(handler_wii_slug, DolphinWiiHandler)
    from romm_steam_sync.service_layer.save_strategies.handlers.dolphin import DolphinGameCubeHandler
    assert isinstance(handler_gc, DolphinGameCubeHandler)
    assert isinstance(handler_gc_slug, DolphinGameCubeHandler)
    assert CORE_SAVE_STRATEGY_MAP["wii"] == "memory_card_per_game"
    assert CORE_SAVE_STRATEGY_MAP["nintendo-wii"] == "memory_card_per_game"
