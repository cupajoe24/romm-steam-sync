"""Unit tests for SyncView progress updates and indeterminate state transitions."""

from unittest.mock import MagicMock, patch

from romm_steam_sync.config import AppSettings
from romm_steam_sync.ui.views.sync_view import SyncView


def test_updateUiProgress_switchesToIndeterminateOnCalculating():
    # Arrange
    view = SyncView.__new__(SyncView)
    view.settings = AppSettings()
    view.progress_bar = MagicMock()
    view.progress_bar.cget.return_value = "determinate"
    view.status_lbl = MagicMock()
    view.cover_conveyor = MagicMock()
    view.append_log = MagicMock()

    # Act
    view._update_ui_progress(0.25, "Checking RomM library and calculating library changes...")

    # Assert
    view.progress_bar.configure.assert_called_with(mode="indeterminate")
    view.progress_bar.start.assert_called_once()
    view.status_lbl.configure.assert_called_with(text="Checking RomM library and calculating library changes...")
    view.append_log.assert_called_with("[25%] Checking RomM library and calculating library changes...")


def test_updateUiProgress_switchesToIndeterminateOnNegativePct():
    # Arrange
    view = SyncView.__new__(SyncView)
    view.settings = AppSettings()
    view.progress_bar = MagicMock()
    view.progress_bar.cget.return_value = "determinate"
    view.status_lbl = MagicMock()
    view.cover_conveyor = MagicMock()
    view.append_log = MagicMock()

    # Act
    view._update_ui_progress(-1.0, "Checking RomM library and calculating library changes...")

    # Assert
    view.progress_bar.configure.assert_called_with(mode="indeterminate")
    view.progress_bar.start.assert_called_once()
    view.status_lbl.configure.assert_called_with(text="Checking RomM library and calculating library changes...")
    view.append_log.assert_called_with("Checking RomM library and calculating library changes...")


def test_updateUiProgress_switchesBackToDeterminateOnItemProgress():
    # Arrange
    view = SyncView.__new__(SyncView)
    view.settings = AppSettings()
    view.progress_bar = MagicMock()
    view.progress_bar.cget.return_value = "indeterminate"
    view.status_lbl = MagicMock()
    view.cover_conveyor = MagicMock()
    view.append_log = MagicMock()

    # Act
    view._update_ui_progress(0.50, "Added [1/2]: Super Mario World", rom_name="Super Mario World")

    # Assert
    view.progress_bar.stop.assert_called_once()
    view.progress_bar.configure.assert_called_with(mode="determinate")
    view.progress_bar.set.assert_called_with(0.50)
    view.status_lbl.configure.assert_called_with(text="Added [1/2]: Super Mario World")
    view.cover_conveyor.add_cover.assert_called_once_with("Super Mario World", None)


def test_onSyncFinished_resetsProgressBar():
    # Arrange
    view = SyncView.__new__(SyncView)
    view.settings = AppSettings()
    view.progress_bar = MagicMock()
    view.status_lbl = MagicMock()
    view.start_btn = MagicMock()
    view.cancel_btn = MagicMock()
    view.append_log = MagicMock()
    view.winfo_toplevel = MagicMock()

    with patch("romm_steam_sync.ui.views.sync_view.show_sync_complete_modal"):
        # Act
        view._on_sync_finished(True, "Sync complete", 5)

    # Assert
    view.progress_bar.stop.assert_called_once()
    view.progress_bar.configure.assert_called_with(mode="determinate")
    view.progress_bar.set.assert_called_with(1.0)
    view.start_btn.configure.assert_called_with(state="normal")
    view.cancel_btn.configure.assert_called_with(state="disabled")
