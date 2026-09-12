"""Error display and clipboard manager for RomM launcher."""

import logging
import os
import tkinter as tk
from typing import Any, Callable, Optional

import customtkinter as ctk

from romm_steam_sync.ui.theme import (
    COLOR_CARD_BG,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_INFO_HOVER,
    COLOR_SLATE,
    COLOR_SLATE_HOVER,
    COLOR_TEXT,
)

logger = logging.getLogger(__name__)


class ErrorDisplayManager:
    """Manages selectable error textbox, context menu, and clipboard copying."""

    def __init__(
        self,
        window: ctk.CTk,
        card_frame: ctk.CTkFrame,
        detail_label: ctk.CTkLabel,
        status_title_label: ctk.CTkLabel,
        action_frame: ctk.CTkFrame,
        cancel_btn: ctk.CTkButton,
        action_btn: ctk.CTkButton,
        progress_bar: Optional[ctk.CTkProgressBar] = None,
    ):
        """Initialize ErrorDisplayManager.

        Args:
            window: Top-level window hosting the error view.
            card_frame: Status card container frame.
            detail_label: Normal detail text label.
            status_title_label: Title headline label.
            action_frame: Button bar frame.
            cancel_btn: Left/cancel button.
            action_btn: Right/primary action button.
            progress_bar: Optional progress bar to hide on errors.
        """
        self.window = window
        self.card_frame = card_frame
        self.detail_label = detail_label
        self.status_title_label = status_title_label
        self.action_frame = action_frame
        self.cancel_btn = cancel_btn
        self.action_btn = action_btn
        self.progress_bar = progress_bar

        self._last_error_text: str = ""

        # Selectable error text area (hidden until error)
        self.error_textbox = ctk.CTkTextbox(
            self.card_frame,
            height=130,
            font=ctk.CTkFont(family="Consolas" if os.name == "nt" else "Courier", size=12),
            fg_color=COLOR_CARD_BG,
            text_color=COLOR_TEXT,
            wrap="word",
            activate_scrollbars=True,
        )

        self.copy_error_btn = ctk.CTkButton(
            self.action_frame,
            text="Copy Error",
            command=self.copy_error_to_clipboard,
            fg_color=COLOR_SLATE,
            hover_color=COLOR_SLATE_HOVER,
            width=110,
            height=36,
            font=ctk.CTkFont(size=14),
        )

        self._bind_error_textbox_shortcuts()

    def _bind_error_textbox_shortcuts(self) -> None:
        """Bind keyboard shortcuts and right-click context menu to error textbox."""
        try:
            tb = self.error_textbox._textbox
            tb.bind("<Control-a>", self.select_all_error_text)
            tb.bind("<Control-A>", self.select_all_error_text)
            tb.bind("<Command-a>", self.select_all_error_text)
            tb.bind("<Button-3>", self.show_error_context_menu)
            tb.bind("<Button-2>", self.show_error_context_menu)
        except Exception as e:
            logger.debug("Failed binding error textbox shortcuts: %s", e)

    def select_all_error_text(self, event: Optional[Any] = None) -> str:
        """Select all text in error textbox for easy copying.

        Args:
            event: Optional Tk event parameter.

        Returns:
            String indicating event propagation break.
        """
        try:
            self.error_textbox._textbox.tag_add("sel", "1.0", "end")
            return "break"
        except Exception as e:
            logger.debug("Failed selecting all error text: %s", e)
        return ""

    def show_error_context_menu(self, event: Any) -> None:
        """Display right-click popup menu with Copy and Select All options.

        Args:
            event: Tk mouse event containing screen coordinates.
        """
        try:
            menu = tk.Menu(self.window, tearoff=0)
            menu.add_command(label="Copy", command=self.copy_selection_or_error)
            menu.add_command(label="Select All", command=self.select_all_error_text)
            menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            logger.debug("Failed displaying error context menu: %s", e)

    def copy_selection_or_error(self) -> None:
        """Copy active selection in error textbox, or full error text if none selected."""
        try:
            selected_text = self.error_textbox._textbox.get("sel.first", "sel.last")
            if selected_text:
                self.window.clipboard_clear()
                self.window.clipboard_append(selected_text)
                self.window.update()
                logger.info("Copied selected error snippet to clipboard.")
                self.copy_error_btn.configure(text="Copied!")
                self.window.after(2000, self._reset_copy_btn_text)
                return
        except Exception:
            pass
        self.copy_error_to_clipboard()

    def copy_error_to_clipboard(self) -> None:
        """Copy current structured error details to system clipboard."""
        text_to_copy = self._last_error_text
        if not text_to_copy:
            title = self.status_title_label.cget("text")
            detail = self.detail_label.cget("text")
            text_to_copy = f"{title}\n{detail}".strip()

        logger.info("Copying error details to clipboard (%d characters)", len(text_to_copy))
        try:
            self.window.clipboard_clear()
            self.window.clipboard_append(text_to_copy)
            self.window.update()
            self.copy_error_btn.configure(text="Copied!")
            self.window.after(2000, self._reset_copy_btn_text)
        except Exception as e:
            logger.warning("Failed to copy error to clipboard: %s", e)

    def _reset_copy_btn_text(self) -> None:
        """Reset copy error button label back to 'Copy Error'."""
        try:
            self.copy_error_btn.configure(text="Copy Error")
        except Exception as e:
            logger.debug("Failed resetting copy error button label: %s", e)

    def clear_error_state(self) -> None:
        """Reset error display widgets back to normal status presentation."""
        self._last_error_text = ""
        self.copy_error_btn.pack_forget()
        self.error_textbox.grid_forget()
        self.detail_label.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="w")
        self.card_frame.grid_rowconfigure(1, weight=0)

    def show_error_state(
        self,
        title: str,
        message: str,
        header_info: str,
        full_details: Optional[str] = None,
        retry_command: Optional[Callable[[], None]] = None,
        retry_text: str = "Retry",
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        """Display an error in the launcher with selectable text and a copy button.

        Args:
            title: Short error summary displayed in status title.
            message: User-facing error message.
            header_info: Game/ROM context header string.
            full_details: Extended technical diagnostics.
            retry_command: Optional callable invoked if user clicks retry.
            retry_text: Button text for retry action.
            on_close: Optional window close handler.
        """
        display_details = full_details if full_details else message
        self._last_error_text = f"Error: {title}\n{header_info}\n\nDetails:\n{display_details}"

        self.status_title_label.configure(text=title, text_color=COLOR_ERROR)
        self.detail_label.configure(text=message, text_color=COLOR_ERROR)

        try:
            self.detail_label.grid_forget()
            self.error_textbox.configure(state="normal")
            self.error_textbox.delete("1.0", "end")
            self.error_textbox.insert("1.0", display_details)
            self.error_textbox.configure(state="disabled")
            self.error_textbox.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="nsew")
            self.card_frame.grid_rowconfigure(1, weight=1)
        except Exception as e:
            logger.debug("Failed updating error textbox: %s", e)

        if self.progress_bar:
            try:
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
                self.progress_bar.grid_forget()
            except Exception as e:
                logger.debug("Failed hiding progress bar: %s", e)

        self.action_frame.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="ew")

        close_cmd = on_close if on_close else self.window.destroy
        self.cancel_btn.configure(state="normal", text="Close", command=close_cmd)
        self.cancel_btn.pack(side="left")

        self.copy_error_btn.configure(state="normal", text="Copy Error")
        self.copy_error_btn.pack(side="left", padx=(10, 0))

        if retry_command:
            self.action_btn.configure(
                state="normal",
                text=retry_text,
                fg_color=COLOR_INFO_HOVER,
                hover_color=COLOR_INFO,
                command=retry_command,
            )
            self.action_btn.pack(side="right")
        else:
            self.action_btn.pack_forget()
