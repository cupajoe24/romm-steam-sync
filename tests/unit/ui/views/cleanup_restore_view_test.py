"""Unit tests for CleanupRestoreView operations, library refresh, and backup list rendering."""

from unittest.mock import MagicMock, patch

from romm_steam_sync.config import AppSettings
from romm_steam_sync.ui.views.cleanup_restore_view import CleanupRestoreView


def test_refresh_invokesLibrariesAndBackupsRefresh() -> None:
    """Verify refresh calls both refresh_synced_libraries and refresh_backups_list."""
    # Arrange
    view = CleanupRestoreView.__new__(CleanupRestoreView)
    view.refresh_synced_libraries = MagicMock()
    view.refresh_backups_list = MagicMock()

    # Act
    view.refresh()

    # Assert
    view.refresh_synced_libraries.assert_called_once()
    view.refresh_backups_list.assert_called_once()


def test_refreshSyncedLibraries_whenLibrariesFound_populatesDropdownAndEnablesButtons() -> None:
    """Verify synced libraries populate option menu and enable remove buttons."""
    # Arrange
    view = CleanupRestoreView.__new__(CleanupRestoreView)
    view.sync_service = MagicMock()
    view.sync_service.get_synced_libraries.return_value = [
        {"name": "Super Nintendo", "slug": "snes", "count": 12},
        {"name": "Game Boy", "slug": "gb", "count": 5},
    ]
    view.library_dropdown = MagicMock()
    view.remove_selected_btn = MagicMock()
    view.remove_all_btn = MagicMock()

    # Act
    view.refresh_synced_libraries()

    # Assert
    assert len(view.synced_libs_cache) == 2
    view.library_dropdown.configure.assert_called_once_with(
        values=["Super Nintendo (12 games)", "Game Boy (5 games)"]
    )
    view.library_dropdown.set.assert_called_once_with("Super Nintendo (12 games)")
    view.remove_selected_btn.configure.assert_called_once_with(state="normal")
    view.remove_all_btn.configure.assert_called_once_with(state="normal")


def test_refreshSyncedLibraries_whenNoLibrariesFound_disablesButtons() -> None:
    """Verify empty synced libraries disables removal buttons and shows fallback text."""
    # Arrange
    view = CleanupRestoreView.__new__(CleanupRestoreView)
    view.sync_service = MagicMock()
    view.sync_service.get_synced_libraries.return_value = []
    view.library_dropdown = MagicMock()
    view.remove_selected_btn = MagicMock()
    view.remove_all_btn = MagicMock()

    # Act
    view.refresh_synced_libraries()

    # Assert
    assert view.synced_libs_cache == []
    view.library_dropdown.configure.assert_called_once_with(
        values=["No synced libraries found"]
    )
    view.library_dropdown.set.assert_called_once_with("No synced libraries found")
    view.remove_selected_btn.configure.assert_called_once_with(state="disabled")
    view.remove_all_btn.configure.assert_called_once_with(state="disabled")


def test_refreshBackupsList_whenBackupsFound_rendersBackupRows() -> None:
    """Verify existing backups instantiate a row per backup with a rollback button."""
    # Arrange
    view = CleanupRestoreView.__new__(CleanupRestoreView)
    view.backup_mgr = MagicMock()
    view.backup_mgr.list_backups.return_value = [
        {
            "id": "backup_20260913_120000",
            "created_at": "2026-09-13 12:00:00",
            "path": "/mock/path/backup_20260913_120000",
        },
        {
            "id": "backup_20260913_110000",
            "created_at": "2026-09-13 11:00:00",
            "path": "/mock/path/backup_20260913_110000",
        },
    ]
    frame_widget = MagicMock()
    view.backups_list_frame = MagicMock()
    view.backups_list_frame.winfo_children.return_value = [frame_widget]

    with patch("customtkinter.CTkFrame") as mock_ctk_frame, \
         patch("customtkinter.CTkLabel") as mock_ctk_label, \
         patch("customtkinter.CTkButton") as mock_ctk_button, \
         patch("customtkinter.CTkFont"):
        # Act
        view.refresh_backups_list()

        # Assert
        frame_widget.destroy.assert_called_once()
        assert mock_ctk_frame.call_count == 2
        assert mock_ctk_label.call_count == 2
        assert mock_ctk_button.call_count == 2


def test_refreshBackupsList_whenNoBackupsFound_rendersEmptyLabel() -> None:
    """Verify empty backups list destroys child widgets and renders no backups label."""
    # Arrange
    view = CleanupRestoreView.__new__(CleanupRestoreView)
    view.backup_mgr = MagicMock()
    view.backup_mgr.list_backups.return_value = []
    frame_widget = MagicMock()
    view.backups_list_frame = MagicMock()
    view.backups_list_frame.winfo_children.return_value = [frame_widget]

    with patch("customtkinter.CTkLabel") as mock_ctk_label, \
         patch("customtkinter.CTkFont"):
        # Act
        view.refresh_backups_list()

        # Assert
        frame_widget.destroy.assert_called_once()
        mock_ctk_label.assert_called_once()
        args, kwargs = mock_ctk_label.call_args
        assert kwargs.get("text") == "No backups created yet."
