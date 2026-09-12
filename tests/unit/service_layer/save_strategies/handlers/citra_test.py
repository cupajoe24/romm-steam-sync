"""Unit tests for Citra 3DS save strategy and handler."""

from pathlib import Path
import struct
from unittest.mock import MagicMock, patch
import zipfile

from romm_steam_sync.service_layer.save_strategies.handlers.citra import (
    DEFAULT_CITRA_ID0,
    DEFAULT_CITRA_ID1,
    Citra3DSHandler,
)
from romm_steam_sync.service_layer.save_strategies.memory_card_per_game import (
    MemoryCardPerGameStrategy,
    get_handler,
)
from romm_steam_sync.service_layer.save_strategies.registry import (
    CORE_SAVE_STRATEGY_MAP,
    get_save_strategy,
)


def _create_dummy_3ds_ncsd(
    path: Path,
    title_id: int = 0x0004000000054000,
    maker_code: str = "01",
    product_code: str = "CTR-P-AREP",
) -> Path:
    """Helper to construct a mock 3DS NCSD container with NCCH partition 0 at 0x4000."""
    data = bytearray(0x5000)
    data[0x100:0x104] = b"NCSD"
    struct.pack_into("<Q", data, 0x108, title_id)
    struct.pack_into("<I", data, 0x120, 0x20)
    struct.pack_into("<I", data, 0x124, 0x10)

    ncch_offset = 0x4000
    data[ncch_offset + 0x100 : ncch_offset + 0x104] = b"NCCH"
    maker_bytes = maker_code.encode("latin1")
    data[ncch_offset + 0x108 : ncch_offset + 0x108 + len(maker_bytes)] = maker_bytes
    struct.pack_into("<Q", data, ncch_offset + 0x118, title_id)
    prod_bytes = product_code.encode("latin1")
    data[ncch_offset + 0x150 : ncch_offset + 0x150 + len(prod_bytes)] = prod_bytes

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _create_dummy_3ds_zip(
    zip_path: Path,
    inner_filename: str = "Zelda.3ds",
    title_id: int = 0x00040000000EC300,
    maker_code: str = "01",
    product_code: str = "CTR-P-BZLE",
) -> Path:
    """Helper to construct a mock zipped 3DS ROM archive."""
    data = bytearray(0x5000)
    data[0x100:0x104] = b"NCSD"
    struct.pack_into("<Q", data, 0x108, title_id)
    struct.pack_into("<I", data, 0x120, 0x20)
    struct.pack_into("<I", data, 0x124, 0x10)

    ncch_offset = 0x4000
    data[ncch_offset + 0x100 : ncch_offset + 0x104] = b"NCCH"
    maker_bytes = maker_code.encode("latin1")
    data[ncch_offset + 0x108 : ncch_offset + 0x108 + len(maker_bytes)] = maker_bytes
    struct.pack_into("<Q", data, ncch_offset + 0x118, title_id)
    prod_bytes = product_code.encode("latin1")
    data[ncch_offset + 0x150 : ncch_offset + 0x150 + len(prod_bytes)] = prod_bytes

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(inner_filename, bytes(data))
    return zip_path


def _create_dummy_cxi_ncch(
    path: Path,
    title_id: int = 0x0004000000164800,
    maker_code: str = "01",
    product_code: str = "CTR-P-BNDA",
) -> Path:
    """Helper to construct a mock raw NCCH container (.cxi / .app)."""
    data = bytearray(0x300)
    data[0x100:0x104] = b"NCCH"
    maker_bytes = maker_code.encode("latin1")
    data[0x108 : 0x108 + len(maker_bytes)] = maker_bytes
    struct.pack_into("<Q", data, 0x118, title_id)
    prod_bytes = product_code.encode("latin1")
    data[0x150 : 0x150 + len(prod_bytes)] = prod_bytes

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_extractRomMetadata_fromNcsd_returnsTitleIdAndRegion(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    rom_file = tmp_path / "Super Mario 3D Land.3ds"
    _create_dummy_3ds_ncsd(
        rom_file,
        title_id=0x0004000000054000,
        maker_code="01",
        product_code="CTR-P-AREP",
    )

    # Act
    meta = handler.extract_rom_metadata(str(rom_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["title_id"] == "0004000000054000"
    assert meta["title_id_low"] == "00054000"
    assert meta["maker_code"] == "01"
    assert meta["product_code"] == "CTR-P-AREP"
    assert meta["region"] == "EUR"
    assert meta["title"] == "Super Mario 3D Land"


def test_extractRomMetadata_fromZip_returnsTitleIdAndRegion(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    zip_file = tmp_path / "Legend of Zelda, The - A Link Between Worlds (USA).zip"
    _create_dummy_3ds_zip(
        zip_file,
        inner_filename="Legend of Zelda, The - A Link Between Worlds.3ds",
        title_id=0x00040000000EC300,
        maker_code="01",
        product_code="CTR-P-BZLE",
    )

    # Act
    meta = handler.extract_rom_metadata(str(zip_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["title_id"] == "00040000000EC300"
    assert meta["title_id_low"] == "000EC300"
    assert meta["product_code"] == "CTR-P-BZLE"
    assert meta["region"] == "USA"


def test_extractRomMetadata_fromCxi_returnsTitleIdAndRegion(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    rom_file = tmp_path / "Pokemon Moon.cxi"
    _create_dummy_cxi_ncch(
        rom_file,
        title_id=0x0004000000175E00,
        maker_code="01",
        product_code="CTR-P-BNDE",
    )

    # Act
    meta = handler.extract_rom_metadata(str(rom_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["title_id"] == "0004000000175E00"
    assert meta["title_id_low"] == "00175E00"
    assert meta["maker_code"] == "01"
    assert meta["product_code"] == "CTR-P-BNDE"
    assert meta["region"] == "USA"


def test_extractRomMetadata_fallbackFilenameTag_parsesBracketedId(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    rom_file = tmp_path / "Zelda Ocarina of Time 3D [0004000000033500] (Europe).cci"
    rom_file.write_bytes(b"\x00" * 256)

    # Act
    meta = handler.extract_rom_metadata(str(rom_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["title_id"] == "0004000000033500"
    assert meta["title_id_low"] == "00033500"
    assert meta["region"] == "EUR"


def test_getSaveDirectories_returnsCitraSdmcPaths(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    fake_ra = tmp_path / "RetroArch" / "retroarch.exe"
    fake_ra.parent.mkdir(parents=True, exist_ok=True)
    fake_ra.write_text("")

    # Act
    dirs = handler.get_save_directories(configured_retroarch_path=str(fake_ra))

    # Assert
    assert any("Citra" in str(d) and "Nintendo 3DS" in str(d) for d in dirs)


def test_resolveTargetSavePath_constructsCanonicalSdmcZipPath(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    rom_file = tmp_path / "Mario Kart 7.3ds"
    _create_dummy_3ds_ncsd(rom_file, title_id=0x0004000000030800)
    base_sdmc = tmp_path / "saves" / "Citra" / "sdmc" / "Nintendo 3DS"

    # Act
    target = handler.resolve_target_save_path([base_sdmc], str(rom_file))

    # Assert
    expected = (
        base_sdmc
        / DEFAULT_CITRA_ID0
        / DEFAULT_CITRA_ID1
        / "title"
        / "00040000"
        / "00030800"
        / "data"
        / "00000001"
        / "00000001.zip"
    )
    assert target == expected


def test_findExistingSave_withSingleMain_returnsFile(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    rom_file = tmp_path / "Mario Kart 7.3ds"
    _create_dummy_3ds_ncsd(rom_file, title_id=0x0004000000030800)
    base_sdmc = tmp_path / "saves" / "Citra" / "sdmc" / "Nintendo 3DS"
    save_file = (
        base_sdmc
        / DEFAULT_CITRA_ID0
        / DEFAULT_CITRA_ID1
        / "title"
        / "00040000"
        / "00030800"
        / "data"
        / "00000001"
        / "main"
    )
    save_file.parent.mkdir(parents=True, exist_ok=True)
    save_file.write_bytes(b"CITRA_SAVE_DATA_BYTES")

    # Act
    found = handler.find_existing_save([base_sdmc], str(rom_file))

    # Assert
    assert found is not None
    assert found == save_file


def test_findExistingSave_withMultiFile_consolidatesIntoZip(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    rom_file = tmp_path / "Zelda ALBW.zip"
    _create_dummy_3ds_zip(rom_file, title_id=0x00040000000EC300)
    nested_sdmc = tmp_path / "RetroArch" / "saves" / "Citra" / "Citra" / "sdmc" / "Nintendo 3DS"
    data_dir = (
        nested_sdmc
        / DEFAULT_CITRA_ID0
        / DEFAULT_CITRA_ID1
        / "title"
        / "00040000"
        / "000ec300"
        / "data"
        / "00000001"
    )
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "SaveCommon.bin").write_bytes(b"COMMON_DATA")
    (data_dir / "Save_0.bin").write_bytes(b"SLOT_0_DATA")
    (data_dir / "Save_1.bin").write_bytes(b"SLOT_1_DATA")

    # Act
    found = handler.find_existing_save([nested_sdmc], str(rom_file))

    # Assert
    assert found is not None
    assert found.suffix == ".zip"
    assert found.exists()
    with zipfile.ZipFile(found, "r") as zf:
        assert sorted(zf.namelist()) == ["SaveCommon.bin", "Save_0.bin", "Save_1.bin"]


def test_findExistingSave_discoversCustomConsoleIds(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    rom_file = tmp_path / "Mario Kart 7.3ds"
    _create_dummy_3ds_ncsd(rom_file, title_id=0x0004000000030800)
    base_sdmc = tmp_path / "saves" / "Citra" / "sdmc" / "Nintendo 3DS"
    custom_id0 = "11112222333344445555666677778888"
    custom_id1 = "aaaabbbbccccddddeeeeffff00001111"
    save_file = (
        base_sdmc
        / custom_id0
        / custom_id1
        / "title"
        / "00040000"
        / "00030800"
        / "data"
        / "00000001"
        / "main"
    )
    save_file.parent.mkdir(parents=True, exist_ok=True)
    save_file.write_bytes(b"CITRA_SAVE_DATA_CUSTOM")

    # Act
    found = handler.find_existing_save([base_sdmc], str(rom_file))

    # Assert
    assert found is not None
    assert found == save_file


def test_syncPreLaunch_downloadsAndUnpacksZip(tmp_path):
    # Arrange
    strategy = MemoryCardPerGameStrategy()
    rom_file = tmp_path / "roms" / "3ds" / "Super Mario 3D Land.3ds"
    _create_dummy_3ds_ncsd(rom_file, title_id=0x0004000000054000)
    saves_dir = tmp_path / "RetroArch" / "saves" / "Citra" / "sdmc" / "Nintendo 3DS"

    mock_client = MagicMock()
    mock_client.get_saves.return_value = [
        {
            "id": 99,
            "name": "00000001.zip",
            "file_name": "00000001.zip",
            "content_hash": "remotehash123",
            "updated_at": "2026-08-30T12:00:00Z",
        }
    ]

    def _fake_download(save_id, dest):
        dest_p = Path(dest)
        dest_p.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest_p, "w") as zf:
            zf.writestr("SaveCommon.bin", b"DOWNLOADED_COMMON")
            zf.writestr("Save_0.bin", b"DOWNLOADED_SLOT0")
        return True

    mock_client.download_save_content.side_effect = _fake_download

    with patch.object(
        Citra3DSHandler,
        "get_save_directories",
        return_value=[saves_dir],
    ):
        # Act
        action, msg, remote_save, target_path = strategy.sync_pre_launch(
            rom_id=101,
            rom_path=str(rom_file),
            platform_slug="3ds",
            client=mock_client,
            core_name="citra_libretro",
        )

    # Assert
    assert action == "DOWNLOAD"
    assert target_path.exists()
    dest_data_dir = target_path.parent / "00000001"
    assert (dest_data_dir / "SaveCommon.bin").exists()
    assert (dest_data_dir / "Save_0.bin").read_bytes() == b"DOWNLOADED_SLOT0"


def test_syncPostLaunch_uploadsMainSave(tmp_path):
    # Arrange
    strategy = MemoryCardPerGameStrategy()
    rom_file = tmp_path / "Super Mario 3D Land.3ds"
    _create_dummy_3ds_ncsd(rom_file, title_id=0x0004000000054000)
    saves_dir = tmp_path / "RetroArch" / "saves" / "Citra" / "sdmc" / "Nintendo 3DS"
    save_file = (
        saves_dir
        / DEFAULT_CITRA_ID0
        / DEFAULT_CITRA_ID1
        / "title"
        / "00040000"
        / "00054000"
        / "data"
        / "00000001"
        / "main"
    )
    save_file.parent.mkdir(parents=True, exist_ok=True)
    save_file.write_bytes(b"UPDATED_CITRA_SAVE_POST_PLAY")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = []
    mock_client.upload_save.return_value = {"id": 100, "content_hash": "abc"}

    # Act
    success, msg = strategy.sync_post_launch(
        rom_id=101,
        save_path=str(save_file),
        client=mock_client,
        slot="autosave",
        platform_slug="3ds",
        rom_path=str(rom_file),
        core_name="citra_libretro",
    )

    # Assert
    assert success is True
    mock_client.upload_save.assert_called_once_with(
        101, str(save_file), save_id=None, slot="autosave"
    )


def test_syncPostLaunch_uploadViaRomPath_archivesAndUploads(tmp_path):
    # Arrange
    strategy = MemoryCardPerGameStrategy()
    rom_file = tmp_path / "Legend of Zelda.zip"
    _create_dummy_3ds_zip(rom_file, title_id=0x00040000000EC300)
    saves_dir = tmp_path / "RetroArch" / "saves" / "Citra" / "sdmc" / "Nintendo 3DS"
    data_dir = (
        saves_dir
        / DEFAULT_CITRA_ID0
        / DEFAULT_CITRA_ID1
        / "title"
        / "00040000"
        / "000ec300"
        / "data"
        / "00000001"
    )
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "SaveCommon.bin").write_bytes(b"COMMON_BYTES")
    (data_dir / "Save_0.bin").write_bytes(b"SLOT0_BYTES")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = []
    mock_client.upload_save.return_value = {"id": 100, "content_hash": "abc"}

    with patch.object(
        Citra3DSHandler,
        "get_save_directories",
        return_value=[saves_dir],
    ):
        # Act
        success, msg = strategy.sync_post_launch(
            rom_id=101,
            save_path=str(rom_file),
            client=mock_client,
            slot="autosave",
            platform_slug="3ds",
            rom_path=str(rom_file),
            core_name="citra_libretro",
        )

    # Assert
    assert success is True
    expected_zip = data_dir.parent / "00000001.zip"
    mock_client.upload_save.assert_called_once_with(
        101, str(expected_zip), save_id=None, slot="autosave"
    )


def test_findExistingSave_matchesLowercaseHexTitleId(tmp_path):
    # Arrange
    handler = Citra3DSHandler()
    rom_file = tmp_path / "Zelda ALBW.3ds"
    _create_dummy_3ds_ncsd(rom_file, title_id=0x00040000000EC300)
    base_sdmc = tmp_path / "saves" / "Citra" / "sdmc" / "Nintendo 3DS"
    save_file = (
        base_sdmc
        / DEFAULT_CITRA_ID0
        / DEFAULT_CITRA_ID1
        / "title"
        / "00040000"
        / "000ec300"
        / "data"
        / "00000001"
        / "main"
    )
    save_file.parent.mkdir(parents=True, exist_ok=True)
    save_file.write_bytes(b"ZELDA_ALBW_SAVE")

    # Act
    found = handler.find_existing_save([base_sdmc], str(rom_file))

    # Assert
    assert found is not None
    assert found == save_file


def test_getHandler_mapsCitraCoresToHandler():
    # Arrange & Act
    strat = get_save_strategy("citra_libretro", "3ds")
    strat2 = get_save_strategy("citra2018_libretro", "n3ds")
    handler = get_handler("citra_libretro", "3ds")
    handler2 = get_handler(core_name="", platform_slug="nintendo-3ds")

    # Assert
    assert isinstance(strat, MemoryCardPerGameStrategy)
    assert isinstance(strat2, MemoryCardPerGameStrategy)
    assert isinstance(handler, Citra3DSHandler)
    assert isinstance(handler2, Citra3DSHandler)
    assert CORE_SAVE_STRATEGY_MAP["citra_libretro"] == "memory_card_per_game"
    assert CORE_SAVE_STRATEGY_MAP["3ds"] == "memory_card_per_game"
