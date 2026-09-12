"""Status card view and action button bar for the RomM launcher window."""

import logging
from typing import Any, Callable, Optional

import customtkinter as ctk

from romm_steam_sync.ui.theme import (
    COLOR_INFO,
    COLOR_NEUTRAL,
    COLOR_NEUTRAL_HOVER,
    COLOR_TEXT,
)

logger = logging.getLogger(__name__)


class StatusCardView:
    """Manages the main card frame, status text, progress bar, and action buttons."""

    def __init__(self, master: ctk.CTkFrame):
        """Initialize StatusCardView.

        Args:
            master: Parent container widget.
        """
        self.master = master

        # Status Card Frame
        self.card_frame = ctk.CTkFrame(master, corner_radius=10)
        self.card_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.card_frame.grid_columnconfigure(0, weight=1)

        self.status_title_label = ctk.CTkLabel(
            self.card_frame,
            text="Inspecting local system...",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
            wraplength=540,
            justify="left",
        )
        self.status_title_label.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")

        self.detail_label = ctk.CTkLabel(
            self.card_frame,
            text="Checking local ROM storage and database records...",
            font=ctk.CTkFont(size=14),
            text_color="gray",
            anchor="w",
            justify="left",
            wraplength=540,
        )
        self.detail_label.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="w")

        # Progress Bar (hidden by default)
        self.progress_bar = ctk.CTkProgressBar(self.card_frame)
        self.progress_bar.set(0.0)

        # Action Button Bar
        self.action_frame = ctk.CTkFrame(master, fg_color="transparent")
        self.action_frame.grid_columnconfigure(0, weight=1)

        self.cancel_btn = ctk.CTkButton(
            self.action_frame,
            text="Close",
            command=None,
            fg_color=COLOR_NEUTRAL_HOVER,
            hover_color=COLOR_NEUTRAL,
            width=100,
            height=36,
            font=ctk.CTkFont(size=14),
        )
        self.cancel_btn.pack(side="left")

        self.action_btn = ctk.CTkButton(
            self.action_frame,
            text="Please Wait...",
            command=None,
            state="disabled",
            width=160,
            height=36,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.action_btn.pack(side="right")

    def set_status(
        self,
        title: str,
        detail: str,
        title_color: Optional[str] = None,
        detail_color: Optional[str] = COLOR_TEXT,
    ) -> None:
        """Update status title and detail descriptions.

        Args:
            title: Headline status text.
            detail: Detailed description text.
            title_color: Optional text color for headline.
            detail_color: Optional text color for detail label.
        """
        if title_color:
            self.status_title_label.configure(text=title, text_color=title_color)
        else:
            self.status_title_label.configure(text=title)

        if detail_color:
            self.detail_label.configure(text=detail, text_color=detail_color)
        else:
            self.detail_label.configure(text=detail)

    def show_progress_bar(self, mode: str = "determinate") -> None:
        """Display progress bar in card frame.

        Args:
            mode: Progress bar mode ('determinate' or 'indeterminate').
        """
        self.progress_bar.grid(row=2, column=0, padx=15, pady=(5, 15), sticky="ew")
        self.progress_bar.configure(mode=mode)
        if mode == "indeterminate":
            self.progress_bar.start()
        else:
            self.progress_bar.set(0.0)

    def hide_progress_bar(self) -> None:
        """Hide progress bar from card frame."""
        try:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.grid_forget()
        except Exception as e:
            logger.debug("Failed hiding progress bar: %s", e)

    def set_progress(self, pct: float, status_text: Optional[str] = None) -> None:
        """Update progress bar percentage and optional detail text.

        Args:
            pct: Float progress value between 0.0 and 1.0.
            status_text: Optional updated detail label text.
        """
        self.progress_bar.set(pct)
        if status_text:
            self.detail_label.configure(text=status_text)

    def show_action_frame(self) -> None:
        """Ensure action button frame is positioned in window grid."""
        self.action_frame.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="ew")

    def configure_action_button(
        self,
        text: str,
        command: Optional[Callable[[], None]],
        state: str = "normal",
        fg_color: Optional[str] = None,
        hover_color: Optional[str] = None,
    ) -> None:
        """Configure the primary action button.

        Args:
            text: Button label.
            command: Click callback.
            state: Button state ('normal' or 'disabled').
            fg_color: Foreground button color.
            hover_color: Hover button color.
        """
        kwargs: dict[str, Any] = {"text": text, "command": command, "state": state}
        if fg_color:
            kwargs["fg_color"] = fg_color
        if hover_color:
            kwargs["hover_color"] = hover_color
        self.action_btn.configure(**kwargs)
        self.action_btn.pack(side="right")

    def hide_action_button(self) -> None:
        """Hide primary action button."""
        self.action_btn.pack_forget()

    def configure_cancel_button(
        self,
        text: str = "Close",
        command: Optional[Callable[[], None]] = None,
        state: str = "normal",
        fg_color: Optional[str] = None,
        hover_color: Optional[str] = None,
    ) -> None:
        """Configure the cancel/secondary button.

        Args:
            text: Button label.
            command: Click callback.
            state: Button state ('normal' or 'disabled').
            fg_color: Foreground button color.
            hover_color: Hover button color.
        """
        kwargs: dict[str, Any] = {"text": text, "state": state}
        if command:
            kwargs["command"] = command
        if fg_color:
            kwargs["fg_color"] = fg_color
        if hover_color:
            kwargs["hover_color"] = hover_color
        self.cancel_btn.configure(**kwargs)
        self.cancel_btn.pack(side="left")
