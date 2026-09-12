"""Unit tests for SteamGuardModal and run_with_steam_guard modal launcher."""

from unittest.mock import MagicMock, patch

from romm_steam_sync.ui.components.steam_guard_modal import run_with_steam_guard


def test_runWithSteamGuard_whenSteamRunning_displaysModal():
    # Arrange
    with patch("romm_steam_sync.ui.components.steam_guard_modal.SteamGuard.is_steam_running", return_value=True), \
         patch("romm_steam_sync.ui.components.steam_guard_modal.SteamGuardModal") as mock_modal:
        proceed_cb = MagicMock()
        parent = MagicMock()

        # Act
        run_with_steam_guard(parent, on_proceed=proceed_cb)

        # Assert
        mock_modal.assert_called_once_with(parent, on_proceed=proceed_cb)
        proceed_cb.assert_not_called()


def test_runWithSteamGuard_whenSteamClosed_callsProceedImmediately():
    # Arrange
    with patch("romm_steam_sync.ui.components.steam_guard_modal.SteamGuard.is_steam_running", return_value=False), \
         patch("romm_steam_sync.ui.components.steam_guard_modal.SteamGuardModal") as mock_modal:
        proceed_cb = MagicMock()
        parent = MagicMock()

        # Act
        run_with_steam_guard(parent, on_proceed=proceed_cb)

        # Assert
        mock_modal.assert_not_called()
        proceed_cb.assert_called_once()
