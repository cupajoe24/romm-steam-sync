"""Unit tests for ErrorDisplayManager component."""

from unittest.mock import MagicMock, patch
import pytest

from romm_steam_sync.launcher.views.error_view import ErrorDisplayManager


def test_errorDisplayManager_showErrorStateConfiguresWidgets():
    # Arrange
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f"Tkinter not available in environment: {e}")

    try:
        card = ctk.CTkFrame(root)
        detail = ctk.CTkLabel(card, text="")
        title = ctk.CTkLabel(card, text="")
        action_frame = ctk.CTkFrame(root)
        cancel_b = ctk.CTkButton(action_frame, text="")
        action_b = ctk.CTkButton(action_frame, text="")

        manager = ErrorDisplayManager(
            window=root,
            card_frame=card,
            detail_label=detail,
            status_title_label=title,
            action_frame=action_frame,
            cancel_btn=cancel_b,
            action_btn=action_b,
        )

        mock_retry = MagicMock()

        # Act
        manager.show_error_state(
            title="Download Failed",
            message="Server timed out",
            header_info="Game: Metroid Fusion",
            full_details="Traceback details...",
            retry_command=mock_retry,
            retry_text="Retry Download",
        )

        # Assert
        assert title.cget("text") == "Download Failed"
        assert detail.cget("text") == "Server timed out"
        assert "Traceback details..." in manager.error_textbox.get("1.0", "end")
        assert action_b.cget("text") == "Retry Download"
        assert manager.copy_error_btn.cget("text") == "Copy Error"
    finally:
        root.destroy()


def test_errorDisplayManager_copyErrorToClipboard():
    # Arrange
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f"Tkinter not available in environment: {e}")

    try:
        card = ctk.CTkFrame(root)
        detail = ctk.CTkLabel(card, text="Error detail message")
        title = ctk.CTkLabel(card, text="Fatal Error")
        action_frame = ctk.CTkFrame(root)
        cancel_b = ctk.CTkButton(action_frame, text="")
        action_b = ctk.CTkButton(action_frame, text="")

        manager = ErrorDisplayManager(
            window=root,
            card_frame=card,
            detail_label=detail,
            status_title_label=title,
            action_frame=action_frame,
            cancel_btn=cancel_b,
            action_btn=action_b,
        )

        with patch.object(root, "clipboard_clear") as mock_clear, \
             patch.object(root, "clipboard_append") as mock_append, \
             patch.object(root, "update"):
            # Act
            manager.copy_error_to_clipboard()

            # Assert
            mock_clear.assert_called_once()
            mock_append.assert_called_once()
            assert "Fatal Error" in mock_append.call_args[0][0]
    finally:
        root.destroy()


def test_errorDisplayManager_clearErrorState():
    # Arrange
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f"Tkinter not available in environment: {e}")

    try:
        card = ctk.CTkFrame(root)
        detail = ctk.CTkLabel(card, text="")
        title = ctk.CTkLabel(card, text="")
        action_frame = ctk.CTkFrame(root)
        cancel_b = ctk.CTkButton(action_frame, text="")
        action_b = ctk.CTkButton(action_frame, text="")

        manager = ErrorDisplayManager(
            window=root,
            card_frame=card,
            detail_label=detail,
            status_title_label=title,
            action_frame=action_frame,
            cancel_btn=cancel_b,
            action_btn=action_b,
        )

        manager.show_error_state(title="Error", message="Fail", header_info="Game")

        # Act
        manager.clear_error_state()

        # Assert
        assert manager._last_error_text == ""
    finally:
        root.destroy()
