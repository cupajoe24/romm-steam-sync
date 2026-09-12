"""Unit tests for RomDownloadService."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import zipfile

from romm_steam_sync.launcher.services.download_service import RomDownloadService


def test_downloadRom_extractsDiscArchive(tmp_path):
    # Arrange
    db_session = MagicMock()
    db = MagicMock()
    db_session.__enter__.return_value = db
    db_session.__exit__.return_value = None

    download_dir = tmp_path / "roms"
    dest_dir = download_dir / "ps1"
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_target = dest_dir / "Crash Bandicoot.zip"

    mock_client = MagicMock()

    def fake_download(rom_id, target_path, file_name=None, progress_callback=None):
        with zipfile.ZipFile(target_path, "w") as zf:
            zf.writestr("Crash Bandicoot.cue", 'FILE "Crash Bandicoot.bin" BINARY\n')
            zf.writestr("Crash Bandicoot.bin", b"\x00" * 2048)
        if progress_callback:
            progress_callback(2048, 2048)
        return True

    mock_client.download_rom_content.side_effect = fake_download
    progress_updates = []

    service = RomDownloadService(db_session=db_session)

    # Act
    success, final_path, err = service.download_rom(
        rom_id=101,
        rom_name="Crash Bandicoot",
        file_name="Crash Bandicoot.zip",
        platform_slug="ps1",
        download_dir=str(download_dir),
        romm_url="http://example.com",
        api_key="key",
        progress_callback=lambda pct, msg: progress_updates.append((pct, msg)),
        client=mock_client,
    )

    # Assert
    assert success is True
    assert err is None
    assert not zip_target.exists()
    game_dir = dest_dir / "Crash Bandicoot"
    assert game_dir.exists() and game_dir.is_dir()
    cue_file = game_dir / "Crash Bandicoot.cue"
    assert final_path == cue_file
    assert cue_file.exists()
    assert len(progress_updates) > 0

    db.installs.add.assert_called_once()
    added_install = db.installs.add.call_args[0][0]
    assert added_install.rom_id == 101
    assert added_install.file_path == str(cue_file)


def test_downloadRom_preservesCartridgeArchive(tmp_path):
    # Arrange
    db_session = MagicMock()
    db = MagicMock()
    db_session.__enter__.return_value = db
    db_session.__exit__.return_value = None

    download_dir = tmp_path / "roms"
    dest_dir = download_dir / "snes"
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_target = dest_dir / "Super Mario World.zip"

    mock_client = MagicMock()

    def fake_download(rom_id, target_path, file_name=None, progress_callback=None):
        with zipfile.ZipFile(target_path, "w") as zf:
            zf.writestr("smw.sfc", b"\x00" * 1024)
        return True

    mock_client.download_rom_content.side_effect = fake_download
    service = RomDownloadService(db_session=db_session)

    # Act
    success, final_path, err = service.download_rom(
        rom_id=202,
        rom_name="Super Mario World",
        file_name="Super Mario World.zip",
        platform_slug="snes",
        download_dir=str(download_dir),
        romm_url="http://example.com",
        api_key="key",
        client=mock_client,
    )

    # Assert
    assert success is True
    assert err is None
    assert zip_target.exists()
    assert final_path == zip_target
    db.installs.add.assert_called_once()


def test_downloadRom_handlesDownloadFailure(tmp_path):
    # Arrange
    db_session = MagicMock()
    mock_client = MagicMock()
    mock_client.download_rom_content.return_value = False

    service = RomDownloadService(db_session=db_session)

    # Act
    success, final_path, err = service.download_rom(
        rom_id=303,
        rom_name="Failed Game",
        file_name="Failed.rom",
        platform_slug="gba",
        download_dir=str(tmp_path / "roms"),
        romm_url="http://example.com",
        api_key="key",
        client=mock_client,
    )

    # Assert
    assert success is False
    assert final_path is None
    assert err is not None
    assert "Could not download ROM file" in err


def test_downloadRom_handlesExtractionFailure(tmp_path):
    # Arrange
    db_session = MagicMock()
    download_dir = tmp_path / "roms"
    dest_dir = download_dir / "ps1"
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_target = dest_dir / "Corrupt.zip"
    zip_target.write_bytes(b"not a valid zip file")

    mock_client = MagicMock()
    mock_client.download_rom_content.return_value = True

    service = RomDownloadService(db_session=db_session)

    # Act
    with patch("romm_steam_sync.launcher.services.download_service.ArchiveExtractor.extract_and_cleanup", side_effect=RuntimeError("Corrupt zip")):
        success, final_path, err = service.download_rom(
            rom_id=404,
            rom_name="Corrupt Game",
            file_name="Corrupt.zip",
            platform_slug="ps1",
            download_dir=str(download_dir),
            romm_url="http://example.com",
            api_key="key",
            client=mock_client,
        )

    # Assert
    assert success is False
    assert final_path is None
    assert "Failed extracting downloaded ROM archive" in str(err)
