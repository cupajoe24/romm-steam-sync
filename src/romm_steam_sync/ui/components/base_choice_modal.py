"""Base modal dialog prompting the user for an action choice with callback dispatch."""

from typing import Any, Callable, Optional

import customtkinter as ctk


class BaseChoiceModal(ctk.CTkToplevel):
    """Base modal dialog prompting user for a choice and triggering a callback.

    Attributes:
        on_choice: Callback receiving the user's choice string.
        selected_choice: The choice string selected by the user, if any.
        default_choice: Action chosen if window is closed without explicit button click.
    """

    def __init__(
        self,
        parent: Any,
        title: str = "Prompt",
        geometry: str = "580x300",
        on_choice: Optional[Callable[[str], None]] = None,
        default_choice: str = "cancel",
    ) -> None:
        """Initialize BaseChoiceModal dialog.

        Args:
            parent: Parent tkinter widget.
            title: Modal window title.
            geometry: Window geometry string (e.g. '580x300').
            on_choice: Optional callback receiving the chosen string.
            default_choice: Action chosen if window is closed without explicit button click.
        """
        super().__init__(parent)
        self.on_choice = on_choice
        self.selected_choice: Optional[str] = None
        self.default_choice = default_choice

        self.title(title)
        self.geometry(geometry)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)

        self.protocol("WM_DELETE_WINDOW", lambda: self._select(self.default_choice))

    def _select(self, choice: str) -> None:
        """Handle user selection, destroy modal, and trigger callback.

        Args:
            choice: User selection action string.
        """
        self.selected_choice = choice
        self.destroy()
        if self.on_choice:
            self.on_choice(choice)
