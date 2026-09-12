"""Unit tests for LauncherWindow UI orchestration and lifecycle."""

from pathlib import Path
import threading
from unittest.mock import MagicMock, patch
import pytest

from romm_steam_sync.launcher.app import LauncherWindow


@pytest.fixture
def mock_launcher_env(tmp_path):
    """Fixture providing mocked database session and app settings."""
    with patch("romm_steam_sync.launcher.app.DatabaseSession") as mock_db, \
         patch("romm_steam_sync.launcher.app.AppSettings") as mock_settings:
        settings_inst = MagicMock()
        settings_inst.romm_url = "http://romm.example.com"
        settings_inst.api_key = "key"
        settings_inst.download_dir = str(tmp_path / "roms")
        settings_inst.retroarch_path = "C:/RetroArch/retroarch.exe"
        settings_inst.core_mappings = {}
        settings_inst.save_sync_enabled = True
        mock_settings.load.return_value = settings_inst

        db_instance = MagicMock()
        db_instance.__enter__.return_value = db_instance
        db_instance.__exit__.return_value = None
        db_instance.roms.get.return_value = None
        db_instance.roms.get_siblings.return_value = []
        db_instance.installs.get.return_value = None
        mock_db.return_value = db_instance

        yield settings_inst, db_instance


def test_launcherWindowClass_initialization_setsUpWindowAndWidgets(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            # Act
            app = LauncherWindow(rom_id=101, platform_slug="snes")

            # Assert
            assert app.rom_id == 101
            assert app.platform_slug == "snes"
            assert app.title() == "RomM Steam Sync Launcher"
            assert app.status_card is not None
            assert app.error_manager is not None
            assert app.version_select_view is not None
            assert app.file_resolver is not None
            assert app.download_service is not None
            assert app.process_supervisor is not None
            assert app.save_coordinator is not None
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_clearTopmost_clearsTopmostAttribute(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")

            with patch.object(app, "attributes") as mock_attrs:
                # Act
                app._clear_topmost()

                # Assert
                mock_attrs.assert_called_with("-topmost", False)
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_onWindowClose_preventsCloseWhenGameRunning(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")
            app.is_game_running = True

            with patch.object(app, "destroy") as mock_destroy:
                # Act
                app._on_window_close()

                # Assert
                mock_destroy.assert_not_called()

            app.is_game_running = False
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_onWindowClose_destroysWindowWhenGameNotRunning(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")
            app.is_game_running = False

            with patch.object(app, "destroy") as mock_destroy:
                # Act
                app._on_window_close()

                # Assert
                mock_destroy.assert_called_once()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_safeAfter_catchesTclErrorsSilently(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")

            with patch.object(app, "after", side_effect=RuntimeError("Tcl interpreter died")):
                # Act - should not raise exception
                app._safe_after(100, lambda: None)

            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_showPromptInstallState_configuresInstallPrompt(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")
            app.rom_name = "Super Mario World"
            app.file_name = "Super Mario World.sfc"
            app.file_size = 1024 * 1024 * 4

            # Act
            app._show_prompt_install_state()

            # Assert
            assert "ROM Not Found Locally" in app.status_title_label.cget("text")
            assert "4 MB" in app.detail_label.cget("text")
            assert app.action_btn.cget("text") == "Install ROM"
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_showReadyToLaunchState_startsCountdown(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")
            app.rom_name = "Super Mario World"
            app.local_file_path = "/roms/snes/smw.sfc"

            # Act
            app._show_ready_to_launch_state()

            # Assert
            assert "Ready to Launch" in app.status_title_label.cget("text")
            assert app.auto_launch_timer is not None
            assert app.cancel_btn.cget("text") == "Cancel"

            # Cleanup timer
            app._cancel_auto_launch()
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_cancelAutoLaunch_cancelsTimerAndShowsLaunchNow(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")
            app.local_file_path = "/roms/snes/smw.sfc"
            app.auto_launch_timer = threading.Timer(10.0, lambda: None)

            # Act
            app._cancel_auto_launch()

            # Assert
            assert app.auto_launch_timer is None
            assert "Launch Cancelled" in app.status_title_label.cget("text")
            assert app.action_btn.cget("text") == "Launch Now"
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_startDownload_transitionsStateToDownloading(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"), \
             patch("threading.Thread") as mock_thread_cls:
            app = LauncherWindow(rom_id=101, platform_slug="snes")

            # Act
            app._start_download()

            # Assert
            assert app.is_downloading is True
            assert "Downloading ROM..." in app.status_title_label.cget("text")
            assert app.action_btn.cget("text") == "Downloading..."
            mock_thread_cls.assert_any_call(target=app._download_worker, daemon=True)
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_executeLaunch_missingLocalPathShowsError(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")
            app.local_file_path = "/nonexistent/game.sfc"

            # Act
            app._execute_launch()

            # Assert
            assert "Error" in app.status_title_label.cget("text")
            assert "does not exist on disk" in app.detail_label.cget("text")
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_inspectSingleRomState_delegatesToRomResolver(mock_launcher_env, tmp_path):
    # Arrange
    settings, db = mock_launcher_env
    game_file = tmp_path / "roms" / "snes" / "smw.sfc"
    game_file.parent.mkdir(parents=True, exist_ok=True)
    game_file.write_bytes(b"\x00" * 512)

    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"), \
             patch("romm_steam_sync.launcher.app.RomMApiClient"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")
            app._safe_after = lambda ms, func, *args: func(*args)

            with patch.object(app.file_resolver, "resolve_local_rom", return_value=game_file):
                # Act
                app._inspect_single_rom_state()

                # Assert
                assert app.local_file_path == str(game_file)
                assert "Ready to Launch" in app.status_title_label.cget("text")

            app._cancel_auto_launch()
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_onServerUnreachable_configuresContinueButton(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")
            app.local_file_path = "/roms/snes/game.sfc"

            # Act
            app._on_server_unreachable()

            # Assert
            assert "RomM Server Unreachable" in app.status_title_label.cget("text")
            assert app.action_btn.cget("text") == "Continue Launch"
            assert app.cancel_btn.cget("text") == "Cancel"
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise


def test_onSyncConflict_configuresConflictButtons(mock_launcher_env):
    # Arrange
    try:
        with patch.object(LauncherWindow, "_inspect_rom_state"):
            app = LauncherWindow(rom_id=101, platform_slug="snes")
            save_target = Path("/saves/game.srm")

            # Act
            app._on_sync_conflict(remote_save={"id": 12}, save_target=save_target)

            # Assert
            assert "Save Conflict Detected" in app.status_title_label.cget("text")
            assert app.cancel_btn.cget("text") == "Use Remote Save"
            assert app.action_btn.cget("text") == "Use Local Save"
            app.destroy()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available: {e}")
        raise
