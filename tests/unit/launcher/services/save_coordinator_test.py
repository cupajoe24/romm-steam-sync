"""Unit tests for SaveCoordinator service."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from romm_steam_sync.launcher.services.save_coordinator import SaveCoordinator


def test_syncPreLaunch_performsPreLaunchSync():
    # Arrange
    settings = MagicMock()
    settings.save_sync_enabled = True
    settings.core_mappings = {}
    settings.retroarch_path = "C:/RetroArch/retroarch.exe"
    settings.default_slot = "autosave"
    settings.romm_url = "http://romm.example.com"
    settings.api_key = "key"

    coordinator = SaveCoordinator(settings=settings)
    mock_client = MagicMock()
    save_path = Path("/saves/game.srm")

    with patch("romm_steam_sync.launcher.services.save_coordinator.SaveSyncEngine.sync_pre_launch") as mock_engine:
        mock_engine.return_value = ("NO_OP", "Save files identical", None, save_path)

        # Act
        action, msg, remote, target = coordinator.sync_pre_launch(
            rom_id=101,
            local_file_path="/roms/snes/game.sfc",
            platform_slug="snes",
            client=mock_client,
        )

        # Assert
        assert action == "NO_OP"
        assert target == save_path
        mock_engine.assert_called_once()


def test_syncPreLaunch_bypassesWhenSaveSyncDisabled(tmp_path):
    # Arrange
    settings = MagicMock()
    settings.save_sync_enabled = False
    settings.core_mappings = {}
    settings.retroarch_path = str(tmp_path / "RetroArch")

    coordinator = SaveCoordinator(settings=settings)

    # Act
    action, msg, remote, target = coordinator.sync_pre_launch(
        rom_id=101,
        local_file_path="/roms/snes/game.sfc",
        platform_slug="snes",
    )

    # Assert
    assert action == "BYPASS"
    assert "Save syncing disabled" in msg


def test_resolveConflictChoice_remoteSave(tmp_path):
    # Arrange
    settings = MagicMock()
    settings.romm_url = "http://romm.example.com"
    settings.api_key = "key"
    settings.core_mappings = {}

    coordinator = SaveCoordinator(settings=settings)
    mock_client = MagicMock()
    save_target = tmp_path / "game.srm"
    save_target.write_bytes(b"local save")
    remote_save = {"id": 999}

    with patch("romm_steam_sync.launcher.services.save_coordinator.quarantine_local_save") as mock_quarantine:
        # Act
        res_target = coordinator.resolve_conflict_choice(
            choice="remote",
            rom_id=101,
            remote_save=remote_save,
            save_target=save_target,
            platform_slug="snes",
            client=mock_client,
        )

        # Assert
        mock_quarantine.assert_called_once_with(str(save_target))
        mock_client.download_save_content.assert_called_once_with(999, str(save_target))
        assert res_target == save_target


def test_resolveConflictChoice_localSave(tmp_path):
    # Arrange
    settings = MagicMock()
    settings.romm_url = "http://romm.example.com"
    settings.api_key = "key"
    settings.default_slot = "autosave"
    settings.core_mappings = {}

    coordinator = SaveCoordinator(settings=settings)
    mock_client = MagicMock()
    save_target = tmp_path / "game.srm"
    save_target.write_bytes(b"local save")
    remote_save = {"id": 999}

    # Act
    res_target = coordinator.resolve_conflict_choice(
        choice="local",
        rom_id=101,
        remote_save=remote_save,
        save_target=save_target,
        platform_slug="snes",
        client=mock_client,
    )

    # Assert
    mock_client.upload_save.assert_called_once_with(101, str(save_target), save_id=999, slot="autosave")
    assert res_target == save_target


def test_syncPostLaunch_ingestsPlaytimeSessionAndUploadsSave(tmp_path):
    # Arrange
    settings = MagicMock()
    settings.save_sync_enabled = True
    settings.device_id = "steam-deck-1"
    settings.romm_url = "http://romm.example.com"
    settings.api_key = "key"
    settings.default_slot = "autosave"
    settings.core_mappings = {}
    settings.retroarch_path = "C:/RetroArch/retroarch.exe"

    coordinator = SaveCoordinator(settings=settings)
    mock_client = MagicMock()
    save_target = tmp_path / "game.srm"
    save_target.write_bytes(b"updated save")

    with patch("romm_steam_sync.launcher.services.save_coordinator.SaveSyncEngine.sync_post_launch") as mock_post_sync, \
         patch("time.sleep"):
        mock_post_sync.return_value = (True, "Uploaded successfully")

        # Act
        coordinator.sync_post_launch(
            rom_id=101,
            local_file_path="/roms/snes/game.sfc",
            platform_slug="snes",
            save_target=save_target,
            session_start_time=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            session_start_mono=100.0,
            client=mock_client,
        )

        # Assert
        mock_client.ingest_play_sessions.assert_called_once()
        mock_post_sync.assert_called_once()
