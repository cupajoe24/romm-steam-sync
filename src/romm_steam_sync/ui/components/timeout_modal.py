"""RomM Server Timeout Modal Dialog for user choice (Retry, Cancel, Revert to Backup)."""

from typing import Any, Callable, Optional

import customtkinter as ctk

from romm_steam_sync.ui.components.base_choice_modal import BaseChoiceModal
from romm_steam_sync.ui.theme import (
    COLOR_ERROR,
    COLOR_ERROR_HOVER,
    COLOR_INFO,
    COLOR_INFO_HOVER,
    COLOR_WARNING,
    COLOR_WARNING_HOVER,
)


class RomMTimeoutModal(BaseChoiceModal):
    """Modal dialog prompting user when RomM API times out during sync pass."""

    def __init__(
        self,
        parent: Any,
        platform_name: str,
        backup_id: Optional[str],
        on_choice: Callable[[str], None],
    ) -> None:
        """Initialize RomMTimeoutModal dialog.

        Args:
            parent: Parent tkinter widget.
            platform_name: Display name of the platform experiencing timeout.
            backup_id: Optional identifier of the pre-sync backup.
            on_choice: Callback receiving user's choice ('retry', 'revert', 'cancel').
        """
        super().__init__(
            parent=parent,
            title="RomM Server Timeout",
            geometry="580x320",
            on_choice=on_choice,
            default_choice="cancel",
        )
        self.platform_name = platform_name
        self.backup_id = backup_id

        # Header Alert
        self.header_label = ctk.CTkLabel(
            self,
            text="RomM Server Timed Out",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_ERROR,
        )
        self.header_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Description
        backup_msg = f" (Pre-sync backup ID: {backup_id})" if backup_id else ""
        desc_text = (
            "The RomM server timed out after 3 retries while fetching data for"
            f" system:\n• {platform_name}\n\nPlease select how you would like"
            f" to proceed{backup_msg}:"
        )

        self.desc_label = ctk.CTkLabel(
            self,
            text=desc_text,
            font=ctk.CTkFont(size=15),
            justify="center",
        )
        self.desc_label.grid(row=1, column=0, padx=20, pady=10)

        # Button Frame
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=2, column=0, padx=20, pady=25)

        # 1. Retry
        self.retry_btn = ctk.CTkButton(
            self.btn_frame,
            text="Retry Fetch",
            command=lambda: self._select("retry"),
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_INFO,
            hover_color=COLOR_INFO_HOVER,
            width=150,
            height=38,
        )
        self.retry_btn.pack(side="left", padx=8)

        # 2. Revert to Backup
        self.revert_btn = ctk.CTkButton(
            self.btn_frame,
            text="Revert to Backup",
            command=lambda: self._select("revert"),
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_WARNING,
            hover_color=COLOR_WARNING_HOVER,
            width=165,
            height=38,
        )
        self.revert_btn.pack(side="left", padx=8)

        # 3. Cancel Sync
        self.cancel_btn = ctk.CTkButton(
            self.btn_frame,
            text="Cancel Sync",
            command=lambda: self._select("cancel"),
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_ERROR,
            hover_color=COLOR_ERROR_HOVER,
            width=140,
            height=38,
        )
        self.cancel_btn.pack(side="left", padx=8)
