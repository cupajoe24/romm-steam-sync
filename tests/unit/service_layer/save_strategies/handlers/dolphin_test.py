"""Unit tests for Dolphin GameCube save strategy handler."""

from pathlib import Path
import struct
from unittest.mock import patch
import zlib

from romm_steam_sync.service_layer.save_strategies.handlers.dolphin import (
    _GC_MAGIC,
    DolphinGameCubeHandler,
    read_gci_header,
)


def _create_dummy_gc_disc(
    path: Path,
    game_code: str = "GM8E",
    maker_code: str = "01",
    title: str = "Mario Party 8",
) -> Path:
    """Helper to construct a mock GameCube disc header (0x60 bytes)."""
    header = bytearray(0x60)
    header[0:4] = game_code.encode("latin1")
    header[4:6] = maker_code.encode("latin1")
    header[0x1C:0x20] = _GC_MAGIC
    title_bytes = title.encode("latin1")
    header[0x20 : 0x20 + len(title_bytes)] = title_bytes
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)
    return path


def _create_dummy_gci(
    path: Path,
    game_code: str = "GM8E",
    maker_code: str = "01",
    internal_name: str = "MarioParty8Save",
) -> Path:
    """Helper to construct a mock GameCube .gci save header (0x28 bytes)."""
    header = bytearray(0x28)
    header[0:4] = game_code.encode("latin1")
    header[4:6] = maker_code.encode("latin1")
    name_bytes = internal_name.encode("latin1")
    header[8 : 8 + len(name_bytes)] = name_bytes
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)
    return path


def test_extractRomMetadata_fromIso_identifiesHeader(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    rom_file = tmp_path / "Mario Party 8.iso"
    _create_dummy_gc_disc(rom_file, game_code="GM8E", maker_code="01", title="Mario Party 8")

    # Act
    meta = handler.extract_rom_metadata(str(rom_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["game_code"] == "GM8E"
    assert meta["maker_code"] == "01"
    assert meta["region"] == "USA"
    assert meta["title"] == "Mario Party 8"


def test_extractRomMetadata_fromRvz_identifiesHeader(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    rvz_file = tmp_path / "Mario Kart - Double Dash!! (USA).rvz"
    prefix = b"RVZ\x01" + b"\x00" * (0x48 - 4)
    gc_header = bytearray(0x60)
    gc_header[0:4] = b"GM4E"
    gc_header[4:6] = b"01"
    gc_header[0x1C:0x20] = b"\xc2\x33\x9f\x3d"
    title_bytes = b"Mario Kart Double Dash!"
    gc_header[0x20 : 0x20 + len(title_bytes)] = title_bytes
    rvz_file.write_bytes(prefix + gc_header)

    # Act
    meta = handler.extract_rom_metadata(str(rvz_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["game_code"] == "GM4E"
    assert meta["maker_code"] == "01"
    assert meta["region"] == "USA"
    assert meta["title"] == "Mario Kart Double Dash!"


def test_extractRomMetadata_fromCiso_identifiesHeader(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    ciso_file = tmp_path / "Super Smash Bros. Melee.ciso"
    raw_iso = bytearray(0x60)
    raw_iso[0:4] = b"GALE"
    raw_iso[4:6] = b"01"
    raw_iso[0x1C:0x20] = b"\xc2\x33\x9f\x3d"
    raw_iso[0x20 : 0x20 + 22] = b"Super Smash Bros Melee"

    ciso_data = bytearray(0x8060)
    ciso_data[0:4] = b"CISO"
    struct.pack_into("<I", ciso_data, 4, 0x8000)
    ciso_data[0x8000:0x8060] = raw_iso
    ciso_file.write_bytes(ciso_data)

    # Act
    meta = handler.extract_rom_metadata(str(ciso_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["game_code"] == "GALE"
    assert meta["maker_code"] == "01"
    assert meta["title"] == "Super Smash Bros Melee"
    assert meta["region"] == "USA"


def test_extractRomMetadata_fromGcz_identifiesHeader(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    gcz_file = tmp_path / "Zelda Wind Waker.gcz"
    raw_iso = bytearray(0x60)
    raw_iso[0:4] = b"GZLE"
    raw_iso[4:6] = b"01"
    raw_iso[0x1C:0x20] = b"\xc2\x33\x9f\x3d"
    raw_iso[0x20 : 0x20 + 16] = b"Zelda Wind Waker"

    decomp_block0 = bytes(raw_iso) + b"\x00" * 0x4000
    comp_block0 = zlib.compress(decomp_block0)

    gcz_header = bytearray(0x18 + 8)
    gcz_header[0:4] = b"\xb1\x0b\xc0\x01"
    struct.pack_into("<I", gcz_header, 4, 0)
    struct.pack_into("<Q", gcz_header, 8, len(decomp_block0))
    struct.pack_into("<I", gcz_header, 16, 0x4000)
    struct.pack_into("<I", gcz_header, 20, 1)
    struct.pack_into("<Q", gcz_header, 24, 0x20)
    gcz_file.write_bytes(gcz_header + comp_block0)

    # Act
    meta = handler.extract_rom_metadata(str(gcz_file))

    # Assert
    assert meta["valid_header"] is True
    assert meta["game_code"] == "GZLE"
    assert meta["maker_code"] == "01"
    assert meta["title"] == "Zelda Wind Waker"


def test_findExistingSave_multiDisc_matchesSharedCard(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    card_a_dir = tmp_path / "RetroArch" / "saves" / "dolphin-emu" / "User" / "GC" / "USA" / "Card A"
    card_a_dir.mkdir(parents=True, exist_ok=True)

    disc1 = tmp_path / "Games" / "Resident Evil 4 (Disc 1).iso"
    disc2 = tmp_path / "Games" / "Resident Evil 4 (Disc 2).iso"
    _create_dummy_gc_disc(disc1, game_code="G4SE", maker_code="08", title="Resident Evil 4")
    _create_dummy_gc_disc(disc2, game_code="G4SE", maker_code="08", title="Resident Evil 4")

    shared_save = card_a_dir / "08-G4SE-ResidentEvil4.gci"
    _create_dummy_gci(shared_save, game_code="G4SE", maker_code="08", internal_name="ResidentEvil4Save")

    # Act
    found_d1 = handler.find_existing_save([card_a_dir], rom_path=str(disc1))
    found_d2 = handler.find_existing_save([card_a_dir], rom_path=str(disc2))

    # Assert
    assert found_d1 == shared_save
    assert found_d2 == shared_save


def test_extractRomMetadata_regionMappings(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    eur_rom = _create_dummy_gc_disc(tmp_path / "EUR.iso", game_code="PZLP", maker_code="01", title="Zelda TP")
    jap_rom_j = _create_dummy_gc_disc(tmp_path / "JAP2.iso", game_code="GALJ", maker_code="01", title="Melee JPN")
    kor_rom = _create_dummy_gc_disc(tmp_path / "KOR.iso", game_code="GALK", maker_code="01", title="Melee KOR")

    # Act & Assert
    assert handler.extract_rom_metadata(str(eur_rom))["region"] == "EUR"
    assert handler.extract_rom_metadata(str(jap_rom_j))["region"] == "JAP"
    assert handler.extract_rom_metadata(str(kor_rom))["region"] == "KOR"


def test_extractRomMetadata_fallbackFilenameTags():
    # Arrange
    handler = DolphinGameCubeHandler()

    # Act & Assert
    assert handler.extract_rom_metadata("C:/Games/The Legend of Zelda (Europe).rvz")["region"] == "EUR"
    meta_jap = handler.extract_rom_metadata("C:/Games/Super Smash Bros (Japan) [GALJ01].ciso")
    assert meta_jap["region"] == "JAP"
    assert meta_jap["game_code"] == "GALJ"
    assert meta_jap["maker_code"] == "01"
    assert handler.extract_rom_metadata("C:/Games/Mario Kart (Korea).wbfs")["region"] == "KOR"
    assert handler.extract_rom_metadata("C:/Games/Metroid Prime.iso")["region"] == "USA"


def test_readGciHeader_extractsCodesAndInternalName(tmp_path):
    # Arrange
    gci_file = tmp_path / "01-GM8E-MarioParty8.gci"
    _create_dummy_gci(gci_file, game_code="GM8E", maker_code="01", internal_name="MarioParty8Save")

    # Act
    header_info = read_gci_header(gci_file)

    # Assert
    assert header_info is not None
    assert header_info["game_code"] == "GM8E"
    assert header_info["maker_code"] == "01"
    assert header_info["internal_name"] == "MarioParty8Save"


def test_getSaveDirectories_returnsRegionCardAPaths(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    ra_exe = tmp_path / "RetroArch" / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")

    with patch(
        "romm_steam_sync.service_layer.save_strategies.handlers.dolphin.RetroArchLauncher.resolve_retroarch_binary",
        return_value=str(ra_exe),
    ):
        # Act
        dirs = handler.get_save_directories(
            configured_retroarch_path=str(ra_exe),
            rom_path=str(tmp_path / "Mario Party 8 (USA).iso"),
        )

        # Assert
        expected_primary = tmp_path / "RetroArch" / "saves" / "dolphin-emu" / "User" / "GC" / "USA" / "Card A"
        assert dirs[0] == expected_primary
        assert any("EUR" in str(d) for d in dirs)
        assert any("JAP" in str(d) for d in dirs)


def test_resolveTargetSavePath_constructsGciPath(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    save_dir = tmp_path / "RetroArch" / "saves" / "dolphin-emu" / "User" / "GC" / "USA" / "Card A"

    # Act
    target_remote = handler.resolve_target_save_path(
        [save_dir],
        rom_path="C:/Games/Mario Party 8.iso",
        remote_filename="01-GM8E-MarioParty8.gci",
    )
    rom_file = tmp_path / "Mario Party 8.iso"
    _create_dummy_gc_disc(rom_file, game_code="GM8E", maker_code="01", title="Mario Party 8")
    target_gen = handler.resolve_target_save_path([save_dir], rom_path=str(rom_file))

    # Assert
    assert target_remote == save_dir / "01-GM8E-MarioParty8.gci"
    assert target_gen == save_dir / "01-GM8E-Mario Party 8.gci"


def test_findExistingSave_matchesByHeaderOrPattern(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    card_a_dir = tmp_path / "RetroArch" / "saves" / "dolphin-emu" / "User" / "GC" / "USA" / "Card A"
    card_a_dir.mkdir(parents=True, exist_ok=True)
    rom_file = tmp_path / "Games" / "Mario Party 8.iso"
    _create_dummy_gc_disc(rom_file, game_code="GM8E", maker_code="01", title="Mario Party 8")
    gci_file = card_a_dir / "custom_named_save.gci"
    _create_dummy_gci(gci_file, game_code="GM8E", maker_code="01", internal_name="MP8Save")

    # Act
    found = handler.find_existing_save([card_a_dir], rom_path=str(rom_file))

    # Assert
    assert found == gci_file

    # Pattern match fallback
    gci_file.unlink()
    raw_card = card_a_dir / "GM8E01.raw"
    raw_card.write_bytes(b"raw memcard")
    found_raw = handler.find_existing_save([card_a_dir], rom_path=str(rom_file))
    assert found_raw == raw_card


def test_migrateLegacySave_movesFileToCardA(tmp_path):
    # Arrange
    handler = DolphinGameCubeHandler()
    card_a_dir = tmp_path / "RetroArch" / "saves" / "dolphin-emu" / "User" / "GC" / "USA" / "Card A"
    rom_file = tmp_path / "Games" / "Mario Party 8.iso"
    _create_dummy_gc_disc(rom_file, game_code="GM8E", maker_code="01", title="Mario Party 8")
    legacy_save = tmp_path / "Games" / "Mario Party 8.gci"
    _create_dummy_gci(legacy_save, game_code="GM8E", maker_code="01", internal_name="MP8Save")

    # Act
    found = handler.find_existing_save([card_a_dir], rom_path=str(rom_file))

    # Assert
    assert found is not None
    assert found.parent == card_a_dir
    assert found.exists()
    assert not legacy_save.exists()


def test_baseDolphinHandler_resolvesDirectoriesAndTags():
    from romm_steam_sync.service_layer.save_strategies.handlers.dolphin import (
        BaseDolphinHandler,
        DolphinHandler,
    )

    class ConcreteDolphinHandler(BaseDolphinHandler):
        def extract_rom_metadata(self, rom_path: str):
            return {}

        def get_save_directories(self, configured_retroarch_path: str = "", rom_path: str = "", platform_slug: str = ""):
            return []

        def resolve_target_save_path(self, save_dirs, rom_path, remote_filename="", remote_ext="", platform_slug=""):
            return Path(".")

        def find_existing_save(self, save_dirs, rom_path, remote_filename="", remote_ext="", platform_slug=""):
            return None

    handler = ConcreteDolphinHandler()
    assert isinstance(handler, BaseDolphinHandler)
    assert isinstance(handler, DolphinHandler)

    # Test region tag parsing
    assert handler.detect_region_from_tags("Game (Europe).iso") == "EUR"
    assert handler.detect_region_from_tags("Game (USA).iso") == "USA"
    assert handler.detect_region_from_tags("Game (Japan).iso") == "JAP"
    assert handler.detect_region_from_tags("Game (Korea).iso") == "KOR"
    assert handler.detect_region_from_tags("Game.iso") is None

    # Test clean string
    assert handler.clean_string_for_matching("Super-Mario_Kart! 8") == "supermariokart8"

    # Test base save directories
    base_dirs = handler.get_base_save_directories()
    assert len(base_dirs) > 0


def test_dolphinGameCubeHandler_directImportAndInheritance():
    from romm_steam_sync.service_layer.save_strategies.handlers.dolphin import (
        BaseDolphinHandler,
    )
    from romm_steam_sync.service_layer.save_strategies.handlers.dolphin_gamecube import (
        DolphinGameCubeHandler,
    )

    gc_handler = DolphinGameCubeHandler()
    assert isinstance(gc_handler, BaseDolphinHandler)

