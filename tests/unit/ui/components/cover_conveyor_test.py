"""Unit tests for RomCoverConveyor and CoverTile UI components."""

from unittest.mock import MagicMock, patch
import pytest

from romm_steam_sync.ui.components.cover_conveyor import CoverTile, RomCoverConveyor


def test_toggleLogs_togglesVisibility():
    # Arrange
    conveyor = RomCoverConveyor.__new__(RomCoverConveyor)
    conveyor.logs_visible = False
    conveyor.log_drawer = MagicMock()
    conveyor.log_toggle_btn = MagicMock()

    # Act 1: Show logs
    conveyor.toggle_logs()

    # Assert 1
    assert conveyor.logs_visible is True
    conveyor.log_drawer.grid.assert_called_once()
    conveyor.log_toggle_btn.configure.assert_called_with(text="Hide Logs")

    # Act 2: Hide logs
    conveyor.toggle_logs()

    # Assert 2
    assert conveyor.logs_visible is False
    conveyor.log_drawer.grid_forget.assert_called_once()
    conveyor.log_toggle_btn.configure.assert_called_with(text="Show Logs")


def test_toggleLogs_updatesGridRowconfigure():
    # Arrange
    conveyor = RomCoverConveyor.__new__(RomCoverConveyor)
    conveyor.logs_visible = False
    conveyor.log_drawer = MagicMock()
    conveyor.log_toggle_btn = MagicMock()
    conveyor.grid_rowconfigure = MagicMock()

    # Act 1: Show logs
    conveyor.toggle_logs()

    # Assert 1
    conveyor.grid_rowconfigure.assert_any_call(1, weight=0)
    conveyor.grid_rowconfigure.assert_any_call(2, weight=1)

    # Act 2: Hide logs
    conveyor.toggle_logs()

    # Assert 2
    conveyor.grid_rowconfigure.assert_any_call(2, weight=0)
    conveyor.grid_rowconfigure.assert_any_call(1, weight=1)


def test_toggleLogs_onboardingStep6_logDrawerVisibleWithinConveyor(tmp_path):
    import customtkinter as ctk
    from romm_steam_sync.config import AppSettings
    from romm_steam_sync.ui.views.onboarding_view import OnboardingView

    try:
        root = ctk.CTk()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        root.geometry("960x700")
        settings = AppSettings(onboarding_complete=False)
        wizard = OnboardingView(root, settings=settings, on_complete=lambda: None)
        wizard.grid(row=0, column=0, sticky="nsew")
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)
        wizard._show_step(6)
        root.update_idletasks()
        root.update()

        conveyor = wizard.step6_conveyor
        assert conveyor.logs_visible is False

        # Toggle logs
        conveyor.toggle_logs()
        root.update_idletasks()
        root.update()

        assert conveyor.logs_visible is True
        conveyor_h = conveyor.winfo_height()
        log_y = conveyor.log_drawer.winfo_y()
        log_h = conveyor.log_drawer.winfo_height()

        # Log drawer must be within conveyor bounds
        assert log_y < conveyor_h, (
            f"Log drawer top ({log_y}) is outside conveyor height ({conveyor_h})"
        )
        assert log_h > 0, "Log drawer height must be positive"
        assert conveyor.log_drawer.winfo_viewable() == 1, "Log drawer must be viewable"
    finally:
        root.destroy()


def test_appendLog_insertsMessageAndScrolls():
    # Arrange
    conveyor = RomCoverConveyor.__new__(RomCoverConveyor)
    conveyor.log_drawer = MagicMock()

    # Act
    conveyor.append_log("Syncing PlayStation 2 library...")

    # Assert
    conveyor.log_drawer.insert.assert_called_with("end", "Syncing PlayStation 2 library...\n")
    conveyor.log_drawer.see.assert_called_with("end")


def test_clear_resetsCardsAndCounter():
    # Arrange
    conveyor = RomCoverConveyor.__new__(RomCoverConveyor)
    card1_widget = MagicMock()
    card2_widget = MagicMock()
    conveyor.cards = [
        {"widget": card1_widget},
        {"widget": card2_widget},
    ]
    conveyor.shortcut_count = 10
    conveyor.count_badge = MagicMock()
    conveyor.placeholder_lbl = MagicMock()
    conveyor.log_drawer = MagicMock()

    # Act
    conveyor.clear()

    # Assert
    assert conveyor.shortcut_count == 0
    assert len(conveyor.cards) == 0
    card1_widget.destroy.assert_called_once()
    card2_widget.destroy.assert_called_once()
    conveyor.count_badge.configure.assert_called_with(text="0 created")
    conveyor.placeholder_lbl.place.assert_called_once()


def test_coverTile_whenPillowTkFails_fallsBackGracefullyWithoutCrash(tmp_path):
    # Arrange
    import customtkinter as ctk
    from PIL import Image

    try:
        root = ctk.CTk()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        root.withdraw()
        img_path = tmp_path / "test_cover.png"
        img = Image.new("RGB", (60, 60), color="blue")
        img.save(img_path)

        # Simulate missing _imagingtk
        with patch("customtkinter.CTkImage", side_effect=ModuleNotFoundError("No module named 'PIL._imagingtk'")):
            tile = CoverTile(root, rom_name="Crash Bandicoot", cover_path=str(img_path))
            root.update_idletasks()

            # Assert tile exists and didn't crash
            assert tile is not None
            assert tile.winfo_exists() == 1
    finally:
        root.destroy()


def test_coverTile_withoutCoverPath_rendersFallbackAndTitle():
    # Arrange
    import customtkinter as ctk

    try:
        root = ctk.CTk()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        root.withdraw()
        tile = CoverTile(root, rom_name="Super Mario 64", cover_path=None)
        root.update_idletasks()

        assert tile is not None
        assert tile._ctk_image is None
        assert tile.winfo_exists() == 1
    finally:
        root.destroy()
