"""Steam Close Guard Modal Dialog."""

import logging
from typing import Any, Callable

import customtkinter as ctk

from romm_steam_sync.adapters.steam_guard import SteamGuard
from romm_steam_sync.ui.theme import (
    COLOR_ERROR,
    COLOR_SUCCESS,
    COLOR_WARNING,
)

logger = logging.getLogger(__name__)


def run_with_steam_guard(parent: Any, on_proceed: Callable[[], None]) -> None:
    """Execute on_proceed if Steam is closed, otherwise present SteamGuardModal.

    Args:
        parent: Parent tkinter widget or root window.
        on_proceed: Callback executed when Steam is confirmed closed.
    """
    if SteamGuard.is_steam_running():
        logger.info("Steam process detected; displaying SteamGuardModal prompt.")
        SteamGuardModal(parent, on_proceed=on_proceed)
    else:
        logger.info("Steam process verified closed; proceeding immediately.")
        on_proceed()


class SteamGuardModal(ctk.CTkToplevel):
    """Modal popup alerting the user to close Steam before modifying shortcuts.vdf."""

    def __init__(
        self, parent: Any, on_proceed: Callable[[], None]
    ) -> None:
        """Initialize SteamGuardModal dialog.

        Args:
            parent: Parent tkinter widget.
            on_proceed: Callback executed when Steam is verified closed and user continues.
        """
        super().__init__(parent)
        self.on_proceed = on_proceed
        self.title("Steam Safety Guard")
        self.geometry("520x300")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.grid_columnconfigure(0, weight=1)

        # Header Alert Label
        self.header_label = ctk.CTkLabel(
            self,
            text="Steam Process Active",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_ERROR,
        )
        self.header_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Description
        self.desc_label = ctk.CTkLabel(
            self,
            text=(
                "Steam is currently running in the background.\n"
                "If Steam remains open while modifying shortcuts.vdf,\n"
                "Steam will silently overwrite all changes upon exit.\n\n"
                "Please close Steam completely before continuing."
            ),
            font=ctk.CTkFont(size=16),
            justify="center",
        )
        self.desc_label.grid(row=1, column=0, padx=20, pady=10)

        # Status indicator
        self.status_label = ctk.CTkLabel(
            self,
            text="Status: Steam is running",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_WARNING,
        )
        self.status_label.grid(row=2, column=0, padx=20, pady=10)

        # Button Frame
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=3, column=0, padx=20, pady=20)

        self.recheck_btn = ctk.CTkButton(
            self.btn_frame,
            text="Re-check Steam",
            command=self.check_status,
            font=ctk.CTkFont(size=15),
            width=150,
        )
        self.recheck_btn.pack(side="left", padx=10)

        self.proceed_btn = ctk.CTkButton(
            self.btn_frame,
            text="Continue Sync",
            command=self._handle_proceed,
            font=ctk.CTkFont(size=15),
            state="disabled",
            width=150,
            fg_color="#27ae60",
            hover_color="#2ec771",
        )
        self.proceed_btn.pack(side="left", padx=10)

        self.check_status()

    def check_status(self) -> bool:
        """Check if Steam process is active and update status indicator label.

        Returns:
            True if Steam is closed, False if still running.
        """
        is_running = SteamGuard.is_steam_running()
        if is_running:
            self.status_label.configure(
                text="Status: Steam process detected. Please close Steam.",
                text_color=COLOR_ERROR,
            )
            self.proceed_btn.configure(state="disabled")
            return False

        self.status_label.configure(
            text="Status: Steam is closed. Safe to proceed!",
            text_color=COLOR_SUCCESS,
        )

        self.proceed_btn.configure(state="normal")
        return True

    def _handle_proceed(self) -> None:
        """Verify Steam is closed before closing dialog and triggering on_proceed."""
        if self.check_status():
            self.destroy()
            self.on_proceed()


def show_sync_complete_modal(parent: Any) -> None:
    """Show notification dialog informing user that Steam can be safely reopened.

    Args:
        parent: Parent tkinter widget.
    """
    dlg = ctk.CTkToplevel(parent)
    dlg.title("Sync Complete")
    dlg.geometry("450x220")
    dlg.resizable(False, False)
    dlg.attributes("-topmost", True)

    label_title = ctk.CTkLabel(
        dlg,
        text="Sync Complete!",
        font=ctk.CTkFont(size=24, weight="bold"),
        text_color="#2ecc71",
    )
    label_title.pack(pady=(25, 10))

    label_msg = ctk.CTkLabel(
        dlg,
        text="All ROM shortcuts and artwork have been saved.\nIt is now safe to launch Steam!",
        font=ctk.CTkFont(size=16),
        justify="center",
    )
    label_msg.pack(pady=10)

    btn = ctk.CTkButton(
        dlg,
        text="Great!",
        command=dlg.destroy,
        font=ctk.CTkFont(size=15),
        width=120,
    )
    btn.pack(pady=15)
