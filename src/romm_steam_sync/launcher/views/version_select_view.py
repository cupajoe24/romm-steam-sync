"""Version and multi-disc selection view for the RomM launcher."""

import logging
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from romm_steam_sync.launcher.formatters import format_version_display
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.ui.theme import (
    COLOR_BORDER,
    COLOR_INFO,
    COLOR_INFO_HOVER,
    COLOR_MUTED,
    COLOR_SUCCESS,
    COLOR_SURFACE,
    COLOR_SURFACE_DARK,
    COLOR_SURFACE_INSET,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
)

logger = logging.getLogger(__name__)


class VersionSelectView:
    """Manages the version / disc selection list and preference persistence."""

    def __init__(
        self,
        card_frame: ctk.CTkFrame,
        db_session: Optional[DatabaseSession] = None,
    ):
        """Initialize VersionSelectView.

        Args:
            card_frame: Container frame in which to place the version scrollable frame.
            db_session: Optional database session provider.
        """
        self.card_frame = card_frame
        self.db_session = db_session or DatabaseSession()

        self.version_var: Optional[ctk.IntVar] = None
        self.always_run_var: Optional[ctk.BooleanVar] = None
        self.version_frame: Optional[ctk.CTkScrollableFrame] = None
        self.always_run_cb: Optional[ctk.CTkCheckBox] = None

    def build_version_list(
        self,
        versions: List[Dict[str, Any]],
        current_rom_id: int,
        canonical_name: str,
    ) -> ctk.IntVar:
        """Construct the scrollable version cards and preference checkbox.

        Args:
            versions: List of version metadata dictionaries.
            current_rom_id: Currently active ROM ID.
            canonical_name: Fallback canonical game title.

        Returns:
            The IntVar variable bound to the radio button group.
        """
        self.cleanup()

        self.version_var = ctk.IntVar(value=current_rom_id)
        self.version_frame = ctk.CTkScrollableFrame(
            self.card_frame,
            height=210,
            fg_color=COLOR_SURFACE_DARK,
            corner_radius=8,
        )
        self.version_frame.grid(row=2, column=0, padx=15, pady=(0, 10), sticky="nsew")
        self.version_frame.grid_columnconfigure(0, weight=1)

        for idx, v in enumerate(versions):
            v_id = v.get("id", 0)
            title_text, subtitle_text = format_version_display(v, canonical_name)
            status_text = "Installed" if v.get("is_installed") else "RomM Cloud"
            status_color = COLOR_SUCCESS if v.get("is_installed") else COLOR_MUTED

            item_card = ctk.CTkFrame(
                self.version_frame,
                fg_color=COLOR_SURFACE,
                corner_radius=6,
                border_width=1,
                border_color=COLOR_BORDER,
            )
            item_card.grid(row=idx, column=0, pady=4, padx=5, sticky="ew")
            item_card.grid_columnconfigure(0, weight=1)

            top_row = ctk.CTkFrame(item_card, fg_color="transparent")
            top_row.grid(row=0, column=0, padx=10, pady=(8, 2), sticky="ew")
            top_row.grid_columnconfigure(0, weight=1)

            rb = ctk.CTkRadioButton(
                top_row,
                text=title_text,
                variable=self.version_var,
                value=v_id,
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            rb.grid(row=0, column=0, sticky="w")

            badge = ctk.CTkLabel(
                top_row,
                text=status_text,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=status_color,
                fg_color=COLOR_SURFACE_INSET,
                corner_radius=4,
                padx=8,
                pady=2,
            )
            badge.grid(row=0, column=1, sticky="e", padx=(10, 0))

            if subtitle_text:
                sub_lbl = ctk.CTkLabel(
                    item_card,
                    text=subtitle_text,
                    font=ctk.CTkFont(size=11),
                    text_color=COLOR_TEXT_MUTED,
                    anchor="w",
                )
                sub_lbl.grid(row=1, column=0, padx=(38, 10), pady=(0, 8), sticky="w")

        self.always_run_var = ctk.BooleanVar(value=False)
        self.always_run_cb = ctk.CTkCheckBox(
            self.card_frame,
            text="Always run this version for this game",
            variable=self.always_run_var,
            font=ctk.CTkFont(size=13),
        )
        self.always_run_cb.grid(row=3, column=0, padx=15, pady=(10, 15), sticky="w")

        return self.version_var

    def get_selected_version(self, default_id: int) -> int:
        """Get the user's selected ROM ID.

        Args:
            default_id: Fallback ID if no selection is made.

        Returns:
            Selected ROM ID.
        """
        if self.version_var:
            return self.version_var.get()
        return default_id

    def persist_preference_if_checked(
        self,
        selected_id: int,
        rom_id: int,
        sibling_group_key: Optional[str] = None,
    ) -> None:
        """Persist default version preference if 'Always run' checkbox was checked.

        Args:
            selected_id: The ROM ID chosen.
            rom_id: Original ROM ID.
            sibling_group_key: Sibling group key if applicable.
        """
        if not self.always_run_var or not self.always_run_var.get():
            return

        try:
            with self.db_session as db:
                if sibling_group_key:
                    db.kv_config.set(f"default_version:{sibling_group_key}", str(selected_id))
                db.kv_config.set(f"default_version:{rom_id}", str(selected_id))
                db.commit()
                logger.info("Persisted default version preference: %s", selected_id)
        except Exception as e:
            logger.warning("Failed persisting default version preference: %s", e)

    def cleanup(self) -> None:
        """Remove version selection widgets from parent card frame."""
        if self.version_frame:
            self.version_frame.grid_forget()
            self.version_frame = None
        if self.always_run_cb:
            self.always_run_cb.grid_forget()
            self.always_run_cb = None
