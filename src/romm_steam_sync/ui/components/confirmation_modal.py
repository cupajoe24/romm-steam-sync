"""Reusable modal dialogs for confirmations and alerts."""

import logging
from typing import Any, Callable, Optional

import customtkinter as ctk

from romm_steam_sync.ui.theme import (
    COLOR_ERROR,
    COLOR_ERROR_HOVER,
    COLOR_SUCCESS,
)

logger = logging.getLogger(__name__)


class ConfirmationModal(ctk.CTkToplevel):
    """Generic modal dialog prompting the user to confirm or cancel an operation."""

    def __init__(
        self,
        parent: Any,
        window_title: str,
        header_title: str,
        message: str,
        confirm_text: str,
        on_confirm: Callable[[], None],
        cancel_text: str = "Cancel",
        header_color: str = COLOR_ERROR,
        confirm_color: str = COLOR_ERROR_HOVER,
        confirm_hover: str = COLOR_ERROR,
        width: int = 500,
        height: int = 240,
    ) -> None:

        """Initialize ConfirmationModal.

        Args:
            parent: Parent tkinter widget or root window.
            window_title: Text displayed in the OS window frame title.
            header_title: Large text heading inside the modal card.
            message: Informational or cautionary prompt text.
            confirm_text: Label for the affirmative action button.
            on_confirm: Callback invoked when the user confirms the action.
            cancel_text: Label for the dismiss button. Defaults to 'Cancel'.
            header_color: Hex color for the header title label.
            confirm_color: Hex background color for the confirm button.
            confirm_hover: Hex hover color for the confirm button.
            width: Modal window width in pixels.
            height: Modal window height in pixels.
        """
        super().__init__(parent)
        self.title(window_title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self._on_confirm = on_confirm

        lbl_title = ctk.CTkLabel(
            self,
            text=header_title,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=header_color,
        )
        lbl_title.pack(pady=(20, 10))

        lbl_msg = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=14),
            justify="center",
        )
        lbl_msg.pack(pady=10)

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(pady=15)

        cancel_btn = ctk.CTkButton(
            btn_box,
            text=cancel_text,
            command=self.destroy,
            width=110,
        )
        cancel_btn.pack(side="left", padx=10)

        confirm_btn = ctk.CTkButton(
            btn_box,
            text=confirm_text,
            command=self._handle_confirm,
            fg_color=confirm_color,
            hover_color=confirm_hover,
            width=140,
        )
        confirm_btn.pack(side="left", padx=10)

    def _handle_confirm(self) -> None:
        """Close dialog and trigger the confirmation callback."""
        self.destroy()
        try:
            self._on_confirm()
        except Exception as e:
            logger.error("Error executing confirmation callback: %s", e)


class AlertModal(ctk.CTkToplevel):
    """Generic alert modal displaying an informational message with an OK button."""

    def __init__(
        self,
        parent: Any,
        window_title: str,
        header_title: str,
        message: str,
        button_text: str = "OK",
        header_color: str = COLOR_SUCCESS,
        width: int = 480,
        height: int = 230,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize AlertModal.

        Args:
            parent: Parent tkinter widget or root window.
            window_title: Text displayed in the OS window frame title.
            header_title: Large text heading inside the modal card.
            message: Informational body text to display.
            button_text: Label for the acknowledge button. Defaults to 'OK'.
            header_color: Hex color for the header title label.
            width: Modal window width in pixels.
            height: Modal window height in pixels.
            on_close: Optional callback invoked when the dialog is dismissed.
        """
        super().__init__(parent)
        self.title(window_title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self._on_close = on_close

        label_title = ctk.CTkLabel(
            self,
            text=header_title,
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=header_color,
        )
        label_title.pack(pady=(25, 10))

        label_msg = ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=15),
            justify="center",
        )
        label_msg.pack(pady=10)

        btn = ctk.CTkButton(
            self,
            text=button_text,
            command=self._handle_close,
            font=ctk.CTkFont(size=15),
            width=120,
        )
        btn.pack(pady=15)

    def _handle_close(self) -> None:
        """Close dialog and trigger the optional on_close callback."""
        self.destroy()
        if self._on_close:
            try:
                self._on_close()
            except Exception as e:
                logger.error("Error executing alert close callback: %s", e)
