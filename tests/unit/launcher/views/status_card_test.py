"""Unit tests for StatusCardView component."""

from unittest.mock import MagicMock
import pytest

from romm_steam_sync.launcher.views.status_card import StatusCardView


def test_statusCardView_initializationCreatesWidgets():
    # Arrange
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f"Tkinter not available in environment: {e}")

    try:
        # Act
        card_view = StatusCardView(master=root)

        # Assert
        assert card_view.card_frame is not None
        assert card_view.status_title_label is not None
        assert card_view.detail_label is not None
        assert card_view.progress_bar is not None
        assert card_view.action_frame is not None
        assert card_view.cancel_btn is not None
        assert card_view.action_btn is not None
    finally:
        root.destroy()


def test_statusCardView_setStatusUpdatesLabels():
    # Arrange
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f"Tkinter not available in environment: {e}")

    try:
        card_view = StatusCardView(master=root)

        # Act
        card_view.set_status(title="Ready to Play", detail="Location: /roms/game.sfc")

        # Assert
        assert card_view.status_title_label.cget("text") == "Ready to Play"
        assert "Location: /roms/game.sfc" in card_view.detail_label.cget("text")
    finally:
        root.destroy()


def test_statusCardView_progressConfiguration():
    # Arrange
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f"Tkinter not available in environment: {e}")

    try:
        card_view = StatusCardView(master=root)

        # Act
        card_view.show_progress_bar(mode="determinate")
        card_view.set_progress(0.75, "Downloading 75%")

        # Assert
        assert card_view.progress_bar.get() == pytest.approx(0.75, 0.01)
        assert card_view.detail_label.cget("text") == "Downloading 75%"

        card_view.hide_progress_bar()
    finally:
        root.destroy()


def test_statusCardView_actionButtonsConfiguration():
    # Arrange
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f"Tkinter not available in environment: {e}")

    try:
        card_view = StatusCardView(master=root)
        mock_cmd = MagicMock()

        # Act
        card_view.configure_action_button(text="Install Now", command=mock_cmd, state="normal")
        card_view.configure_cancel_button(text="Abort", command=mock_cmd, state="normal")

        # Assert
        assert card_view.action_btn.cget("text") == "Install Now"
        assert card_view.cancel_btn.cget("text") == "Abort"
        card_view.hide_action_button()
    finally:
        root.destroy()
