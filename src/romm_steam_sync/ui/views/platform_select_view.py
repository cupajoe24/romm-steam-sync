"""Platform Selection View."""

import logging
from typing import Any, Dict, List, Optional

import customtkinter as ctk

from romm_steam_sync.config import AppSettings
from romm_steam_sync.ui.components.platform_checklist import PlatformChecklistFrame

logger = logging.getLogger(__name__)


class PlatformSelectView(ctk.CTkFrame):
    """View allowing user to select which RomM platforms to sync to Steam."""

    def __init__(self, parent: Any, settings: AppSettings) -> None:
        """Initialize PlatformSelectView.

        Args:
            parent: Parent tkinter widget.
            settings: Active AppSettings instance.
        """
        super().__init__(parent, fg_color="transparent")
        self.settings = settings

        self.grid_columnconfigure(0, weight=1)

        # Header Title
        title_label = ctk.CTkLabel(
            self,
            text="Platform Sync Selection",
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        subtitle_label = ctk.CTkLabel(
            self,
            text="Select which gaming platforms from your RomM library you want to export to Steam.",
            font=ctk.CTkFont(size=16),
            text_color="gray",
        )
        subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Top Control Bar (Refresh, Select All, Deselect All)
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        self.fetch_btn = ctk.CTkButton(
            ctrl_frame,
            text="Refresh Platforms",
            command=self.load_platforms,
            font=ctk.CTkFont(size=15),
            width=140,
        )
        self.fetch_btn.pack(side="left", padx=(0, 10))

        self.select_all_btn = ctk.CTkButton(
            ctrl_frame,
            text="Check All",
            command=self.select_all,
            font=ctk.CTkFont(size=15),
            width=100,
            fg_color="#34495e",
        )
        self.select_all_btn.pack(side="left", padx=5)

        self.deselect_all_btn = ctk.CTkButton(
            ctrl_frame,
            text="Uncheck All",
            command=self.deselect_all,
            font=ctk.CTkFont(size=15),
            width=100,
            fg_color="#34495e",
        )
        self.deselect_all_btn.pack(side="left", padx=5)

        # Scrollable Platforms List Container
        self.checklist = PlatformChecklistFrame(self, label_text="Available RomM Platforms", height=320)
        self.checklist.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.rowconfigure(3, weight=1)

        # Reference to checkbox vars for backwards compatibility with tests and callers
        self.checkbox_vars = self.checklist.checkbox_vars

        # Save Button & Status Label
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=4, column=0, padx=20, pady=15, sticky="ew")

        self.status_label = ctk.CTkLabel(bottom_frame, text="", font=ctk.CTkFont(size=15))
        self.status_label.pack(side="left")

        self.save_btn = ctk.CTkButton(
            bottom_frame,
            text="Save Selections",
            command=self.save_selections,
            font=ctk.CTkFont(size=15, weight="bold"),
            width=150,
            height=38,
        )
        self.save_btn.pack(side="right")

        if self.settings.romm_url:
            self.after(100, self.ensure_populated)

    def _set_status(self, text: str, color: str) -> None:
        """Update status label text and color.

        Args:
            text: Status string.
            color: Hex color string.
        """
        self.status_label.configure(text=text, text_color=color)

    def ensure_populated(self) -> None:
        """Fetch platforms from RomM server if not already populated."""
        if not self.checklist.checkbox_vars:
            self.load_platforms()

    def load_platforms(self) -> None:
        """Fetch platforms from RomM server and populate checkboxes."""
        self.checklist.load_platforms(self.settings, on_status=self._set_status)

    def select_all(self) -> None:
        """Check all platform checkboxes."""
        self.checklist.select_all()

    def deselect_all(self) -> None:
        """Uncheck all platform checkboxes."""
        self.checklist.deselect_all()

    def save_selections(self) -> None:
        """Persist user selected platform slugs to application settings."""
        selected = self.checklist.save_selections(self.settings)
        self._set_status(f"Saved {len(selected)} platforms for sync!", "#2ecc71")
