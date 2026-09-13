"""Unit tests for RommSteamSyncApp main application window."""

from unittest.mock import patch
import pytest

from romm_steam_sync.config import AppSettings


@patch("romm_steam_sync.ui.app.LibraryView")
@patch("romm_steam_sync.ui.app.PlatformSelectView")
@patch("romm_steam_sync.ui.app.SyncView")
@patch("romm_steam_sync.ui.app.CleanupRestoreView")
@patch("romm_steam_sync.ui.app.SettingsView")
@patch("romm_steam_sync.ui.app.OnboardingView")
def test_rommSteamSyncAppClass_onboardingCheck_showsWizardWhenIncomplete(
    mock_onboarding_view,
    mock_settings_view,
    mock_cleanup_view,
    mock_sync_view,
    mock_platform_view,
    mock_library_view,
    tmp_path,
):
    # Arrange
    from romm_steam_sync.ui.app import RommSteamSyncApp

    settings_file = tmp_path / "settings.json"
    with patch.object(AppSettings, "get_settings_file", return_value=settings_file):
        settings = AppSettings(onboarding_complete=False)
        settings.save()

        try:
            with patch.object(AppSettings, "load", return_value=settings):
                # Act
                app = RommSteamSyncApp()
                app.withdraw()

                # Assert
                assert mock_onboarding_view.called
                app.destroy()
        except Exception as e:
            if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
                pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
            raise


@patch("romm_steam_sync.ui.app.LibraryView")
@patch("romm_steam_sync.ui.app.PlatformSelectView")
@patch("romm_steam_sync.ui.app.SyncView")
@patch("romm_steam_sync.ui.app.CleanupRestoreView")
@patch("romm_steam_sync.ui.app.SettingsView")
@patch("romm_steam_sync.ui.app.OnboardingView")
def test_rommSteamSyncAppClass_libraryRefresh_onStartupWhenOnboardingComplete(
    mock_onboarding_view,
    mock_settings_view,
    mock_cleanup_view,
    mock_sync_view,
    mock_platform_view,
    mock_library_view,
    tmp_path,
):
    # Arrange
    from romm_steam_sync.ui.app import RommSteamSyncApp

    settings_file = tmp_path / "settings.json"
    with patch.object(AppSettings, "get_settings_file", return_value=settings_file):
        settings = AppSettings(onboarding_complete=True)
        settings.save()

        try:
            with patch.object(AppSettings, "load", return_value=settings):
                # Act
                app = RommSteamSyncApp()
                app.withdraw()

                # Assert
                assert not mock_onboarding_view.called
                mock_library_view.return_value.refresh.assert_called_once()
                app.destroy()
        except Exception as e:
            if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
                pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
            raise


@patch("romm_steam_sync.ui.app.LibraryView")
@patch("romm_steam_sync.ui.app.PlatformSelectView")
@patch("romm_steam_sync.ui.app.SyncView")
@patch("romm_steam_sync.ui.app.CleanupRestoreView")
@patch("romm_steam_sync.ui.app.SettingsView")
@patch("romm_steam_sync.ui.app.OnboardingView")
def test_navigateToTab_switchesAndTriggersRefresh(
    mock_onboarding_view,
    mock_settings_view,
    mock_cleanup_view,
    mock_sync_view,
    mock_platform_view,
    mock_library_view,
    tmp_path,
):
    # Arrange
    from romm_steam_sync.ui.app import RommSteamSyncApp

    settings_file = tmp_path / "settings.json"
    with patch.object(AppSettings, "get_settings_file", return_value=settings_file):
        settings = AppSettings(onboarding_complete=True)
        settings.save()

        try:
            with patch.object(AppSettings, "load", return_value=settings):
                app = RommSteamSyncApp()
                app.withdraw()
                assert mock_library_view.return_value.refresh.call_count == 1

                # Act 1: Platform Selection tab
                app._navigate_to_tab("Platform Selection")

                # Assert 1
                assert app.tabview.get() == "Platform Selection"
                mock_platform_view.return_value.ensure_populated.assert_called_once()

                # Act 2: Back to Library
                app._navigate_to_tab("Library")

                # Assert 2
                assert app.tabview.get() == "Library"
                assert mock_library_view.return_value.refresh.call_count == 2

                # Act 3: Cleanup & Restore tab
                app._navigate_to_tab("Cleanup & Restore")

                # Assert 3
                assert app.tabview.get() == "Cleanup & Restore"
                mock_cleanup_view.return_value.refresh.assert_called_once()
                app.destroy()
        except Exception as e:
            if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
                pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
            raise


@patch("romm_steam_sync.ui.app.LibraryView")
@patch("romm_steam_sync.ui.app.PlatformSelectView")
@patch("romm_steam_sync.ui.app.SyncView")
@patch("romm_steam_sync.ui.app.CleanupRestoreView")
@patch("romm_steam_sync.ui.app.SettingsView")
@patch("romm_steam_sync.ui.app.OnboardingView")
def test_onOnboardingCompleted_refreshesLibraryAndCleanupViews(
    mock_onboarding_view,
    mock_settings_view,
    mock_cleanup_view,
    mock_sync_view,
    mock_platform_view,
    mock_library_view,
    tmp_path,
):
    # Arrange
    from romm_steam_sync.ui.app import RommSteamSyncApp

    settings_file = tmp_path / "settings.json"
    with patch.object(AppSettings, "get_settings_file", return_value=settings_file):
        settings = AppSettings(onboarding_complete=False)
        settings.save()

        try:
            with patch.object(AppSettings, "load", return_value=settings):
                app = RommSteamSyncApp()
                app.withdraw()
                mock_library_view.return_value.refresh.reset_mock()
                mock_cleanup_view.return_value.refresh.reset_mock()

                # Act
                app._on_onboarding_completed()

                # Assert
                assert app.tabview.get() == "Library"
                mock_library_view.return_value.refresh.assert_called_once()
                mock_cleanup_view.return_value.refresh.assert_called_once()
                app.destroy()
        except Exception as e:
            if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
                pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
            raise

