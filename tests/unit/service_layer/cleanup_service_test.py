"""Unit tests for Advanced Options cleanup and application data purging."""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

from romm_steam_sync.config import AppSettings
from romm_steam_sync.domain import RomInstall
from romm_steam_sync.service_layer.cleanup_service import (
    delete_all_installed_roms,
    purge_all_app_data,
)
from romm_steam_sync.service_layer.db_session import DatabaseSession


def test_deleteAllInstalledRoms_deletesFilesAndClearsDb():
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        db_path = temp_dir / "test_romm.db"
        test_db = DatabaseSession(db_path=db_path)
        rom_dir = temp_dir / "roms"
        rom_dir.mkdir(parents=True, exist_ok=True)
        rom_file = rom_dir / "mario.z64"
        rom_file.write_bytes(b"dummy rom data")
        settings = AppSettings(download_dir=str(rom_dir))

        with test_db as db:
            db.installs.add(
                RomInstall(
                    rom_id=101,
                    file_path=str(rom_file),
                    rom_dir=str(rom_dir),
                    launchable=True,
                )
            )
            db.commit()

        # Act
        ok, msg, count = delete_all_installed_roms(settings=settings, db_session=test_db)

        # Assert
        assert ok is True
        assert count >= 1
        assert not rom_file.exists()
        with test_db as db:
            assert len(db.installs.list_all()) == 0


def test_purgeAllAppData_removesShortcutsAndDeletesConfigDirItems():
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        db_path = temp_dir / "test_romm.db"
        test_db = DatabaseSession(db_path=db_path)
        rom_dir = temp_dir / "roms"
        rom_dir.mkdir(parents=True, exist_ok=True)
        settings = AppSettings(download_dir=str(rom_dir))
        mock_sync_service = MagicMock()
        mock_sync_service.remove_all_synced_libraries.return_value = (True, "Shortcuts removed", 2)

        with patch("romm_steam_sync.service_layer.cleanup_service.get_default_config_dir", return_value=temp_dir):
            dummy_file = temp_dir / "settings.json"
            dummy_file.write_text("{}")

            # Act
            ok, msg = purge_all_app_data(
                settings=settings,
                sync_service=mock_sync_service,
                db_session=test_db,
                skip_steam_guard=True,
            )

            # Assert
            assert ok is True
            mock_sync_service.remove_all_synced_libraries.assert_called_once_with(skip_steam_guard=True)
            assert not dummy_file.exists()
