"""Sync Cancellation Modal Dialog prompting user for Cancel or Rollback choice."""

from typing import Any, Callable, Optional

import customtkinter as ctk

from romm_steam_sync.ui.components.base_choice_modal import BaseChoiceModal
from romm_steam_sync.ui.theme import (
    COLOR_ERROR,
    COLOR_ERROR_HOVER,
    COLOR_NEUTRAL,
    COLOR_NEUTRAL_HOVER,
    COLOR_WARNING,
    COLOR_WARNING_HOVER,
)


class SyncCancelModal(BaseChoiceModal):
    """Modal dialog prompting user when cancelling an active library sync pass."""

    def __init__(
        self,
        parent: Any,
        backup_id: Optional[str] = None,
        on_choice: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize SyncCancelModal dialog.

        Args:
            parent: Parent tkinter widget.
            backup_id: Optional pre-sync backup identifier.
            on_choice: Callback receiving the user's choice string ('cancel', 'rollback', 'resume').
        """
        super().__init__(
            parent=parent,
            title="Cancel Library Synchronization",
            geometry="580x300",
            on_choice=on_choice,
            default_choice="resume",
        )
        self.backup_id = backup_id

        # Header Title
        self.header_label = ctk.CTkLabel(
            self,
            text="Cancel Library Synchronization?",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_ERROR,
        )
        self.header_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Description
        backup_info = f"\nPre-sync backup ID: {backup_id}" if backup_id else ""
        desc_text = (
            f"Library synchronization is currently in progress.{backup_info}\n\n"
            "Would you like to stop sync and keep shortcuts created so far,\n"
            "or cancel and roll back Steam configuration to pre-sync state?"
        )

        self.desc_label = ctk.CTkLabel(
            self,
            text=desc_text,
            font=ctk.CTkFont(size=14),
            justify="center",
        )
        self.desc_label.grid(row=1, column=0, padx=20, pady=10)

        # Action Button Frame
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=2, column=0, padx=20, pady=20)

        # 1. Cancel & Keep
        self.cancel_keep_btn = ctk.CTkButton(
            self.btn_frame,
            text="Cancel & Keep",
            command=lambda: self._select("cancel"),
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_WARNING,
            hover_color=COLOR_WARNING_HOVER,
            width=160,
            height=38,
        )
        self.cancel_keep_btn.pack(side="left", padx=6)

        # 2. Cancel & Rollback
        self.rollback_btn = ctk.CTkButton(
            self.btn_frame,
            text="Cancel & Rollback",
            command=lambda: self._select("rollback"),
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_ERROR,
            hover_color=COLOR_ERROR_HOVER,
            width=175,
            height=38,
        )
        self.rollback_btn.pack(side="left", padx=6)

        # 3. Resume Sync
        self.resume_btn = ctk.CTkButton(
            self.btn_frame,
            text="Resume Sync",
            command=lambda: self._select("resume"),
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_NEUTRAL,
            hover_color=COLOR_NEUTRAL_HOVER,
            width=140,
            height=38,
        )
        self.resume_btn.pack(side="left", padx=6)
