"""Unit tests for SaveSyncEngine high-level interface."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from romm_steam_sync.service_layer.save_sync import SaveSyncEngine


def test_computeSyncAction_delegatesToDecisionTable():
    # Arrange & Act
    action = SaveSyncEngine.compute_sync_action(
        local_exists=False,
        local_hash=None,
        local_mtime=None,
        remote_save={"id": 1, "content_hash": "abc"},
    )

    # Assert
    assert action == "DOWNLOAD"


def test_syncPreLaunch_delegatesToResolvedStrategy():
    # Arrange
    mock_client = MagicMock()
    mock_strat = MagicMock()
    mock_strat.sync_pre_launch.return_value = ("DOWNLOAD", "Downloaded", {"id": 1}, Path("/saves/game.srm"))

    with patch("romm_steam_sync.service_layer.save_sync.get_save_strategy", return_value=mock_strat):
        # Act
        action, msg, remote, local = SaveSyncEngine.sync_pre_launch(
            rom_id=42,
            rom_path="/roms/game.sfc",
            platform_slug="snes",
            client=mock_client,
        )

    # Assert
    assert action == "DOWNLOAD"
    assert local == Path("/saves/game.srm")
    mock_strat.sync_pre_launch.assert_called_once()


def test_syncPostLaunch_delegatesToResolvedStrategy():
    # Arrange
    mock_client = MagicMock()
    mock_strat = MagicMock()
    mock_strat.sync_post_launch.return_value = (True, "Uploaded save")

    with patch("romm_steam_sync.service_layer.save_sync.get_save_strategy", return_value=mock_strat):
        # Act
        success, msg = SaveSyncEngine.sync_post_launch(
            rom_id=42,
            save_path="/saves/game.srm",
            client=mock_client,
            platform_slug="snes",
        )

    # Assert
    assert success is True
    assert msg == "Uploaded save"
    mock_strat.sync_post_launch.assert_called_once()
