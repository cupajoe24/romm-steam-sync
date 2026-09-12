"""Unit tests for LocalRomResolver service."""

from pathlib import Path
from unittest.mock import MagicMock

from romm_steam_sync.domain import RomInstall
from romm_steam_sync.launcher.services.file_resolver import LocalRomResolver


def test_resolveLocalRom_returnsExistingInstallRecord():
    # Arrange
    db_session = MagicMock()
    db = MagicMock()
    db_session.__enter__.return_value = db
    db_session.__exit__.return_value = None

    existing_file = Path("C:/fake/roms/snes/Super Mario World.sfc")
    install = RomInstall(
        rom_id=101,
        file_path=str(existing_file),
        rom_dir=str(existing_file.parent),
        launchable=True,
    )
    db.installs.get.return_value = install

    resolver = LocalRomResolver(db_session=db_session)

    # Act
    with MagicMock() as mock_path:
        # Patch Path.exists for the returned install path
        orig_exists = Path.exists
        try:
            Path.exists = lambda self: True if str(self) == str(existing_file) else orig_exists(self)
            result = resolver.resolve_local_rom(
                rom_id=101,
                rom_name="Super Mario World",
                file_name="Super Mario World.sfc",
                platform_slug="snes",
                download_dir="C:/fake/roms",
            )
        finally:
            Path.exists = orig_exists

    # Assert
    assert result == existing_file


def test_resolveLocalRom_findsExtractedDiscRom(tmp_path):
    # Arrange
    download_dir = tmp_path / "roms"
    dest_dir = download_dir / "dreamcast"
    dest_dir.mkdir(parents=True, exist_ok=True)
    chd_file = dest_dir / "Crazy Taxi.chd"
    chd_file.write_bytes(b"MComprHD" + b"\x00" * 512)

    db_session = MagicMock()
    db = MagicMock()
    db_session.__enter__.return_value = db
    db_session.__exit__.return_value = None
    db.installs.get.return_value = None
    db.installs.list_all.return_value = []

    resolver = LocalRomResolver(db_session=db_session)

    # Act
    result = resolver.resolve_local_rom(
        rom_id=303,
        rom_name="Crazy Taxi",
        file_name="Crazy Taxi.7z",
        platform_slug="dreamcast",
        download_dir=str(download_dir),
    )

    # Assert
    assert result == chd_file
    db.installs.add.assert_called_once()
    added_inst = db.installs.add.call_args[0][0]
    assert added_inst.rom_id == 303
    assert added_inst.file_path == str(chd_file)


def test_resolveLocalRom_preventsHijackingOtherRomFiles(tmp_path):
    # Arrange
    download_dir = tmp_path / "roms"
    dest_dir = download_dir / "ps1"
    dest_dir.mkdir(parents=True, exist_ok=True)
    other_file = dest_dir / "Final Fantasy VII.cue"
    other_file.write_text('FILE "ff7.bin" BINARY')

    db_session = MagicMock()
    db = MagicMock()
    db_session.__enter__.return_value = db
    db_session.__exit__.return_value = None
    db.installs.get.return_value = None
    # Claimed by rom_id 999
    db.installs.list_all.return_value = [
        RomInstall(
            rom_id=999,
            file_path=str(other_file),
            rom_dir=str(dest_dir),
            launchable=True,
        )
    ]

    resolver = LocalRomResolver(db_session=db_session)

    # Act
    result = resolver.resolve_local_rom(
        rom_id=101,
        rom_name="Final Fantasy VII",
        file_name="Final Fantasy VII.zip",
        platform_slug="ps1",
        download_dir=str(download_dir),
    )

    # Assert
    assert result is None
    db.installs.add.assert_not_called()


def test_resolveLocalRom_matchesLooseCandidateFiles(tmp_path):
    # Arrange
    download_dir = tmp_path / "roms"
    dest_dir = download_dir / "gba"
    dest_dir.mkdir(parents=True, exist_ok=True)
    loose_rom = dest_dir / "Pokemon - Emerald Version (USA, Europe).gba"
    loose_rom.write_bytes(b"\x00" * 1024)

    db_session = MagicMock()
    db = MagicMock()
    db_session.__enter__.return_value = db
    db_session.__exit__.return_value = None
    db.installs.get.return_value = None
    db.installs.list_all.return_value = []

    resolver = LocalRomResolver(db_session=db_session)

    # Act
    result = resolver.resolve_local_rom(
        rom_id=505,
        rom_name="Pokemon Emerald",
        file_name="Pokemon - Emerald Version.gba",
        platform_slug="gba",
        download_dir=str(download_dir),
    )

    # Assert
    assert result == loose_rom
    db.installs.add.assert_called_once()
