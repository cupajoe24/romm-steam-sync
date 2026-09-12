"""Modal dialog displaying library synchronization diff and prompting user for sync mode."""

from typing import Any, Callable, Optional

import customtkinter as ctk

from romm_steam_sync.domain.sync_diff import SyncDiff


class SyncDiffModal(ctk.CTkToplevel):
    """Modal dialog prompting user to review diff (additions, removals, unchanged) and select sync mode."""

    def __init__(
        self,
        parent: Any,
        diff: SyncDiff,
        on_choice: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize SyncDiffModal dialog.

        Args:
            parent: Parent tkinter widget.
            diff: Computed SyncDiff aggregate across platforms.
            on_choice: Callback receiving user's choice ('full', 'add_only', 'cancel').
        """
        super().__init__(parent)
        self.diff = diff
        self.on_choice = on_choice
        self.selected_choice: Optional[str] = None

        self.title("Library Synchronization Diff")
        self.geometry("660x520")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header Title
        header_label = ctk.CTkLabel(
            self,
            text="Library Synchronization Diff",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#3498db",
        )
        header_label.grid(row=0, column=0, padx=20, pady=(15, 5))

        subtitle_label = ctk.CTkLabel(
            self,
            text="Review pending library changes from RomM before updating Steam shortcuts.",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 10))

        # Platform Breakdown Scrollable Frame
        scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color=("gray90", "gray14")
        )
        scroll_frame.grid(row=2, column=0, padx=20, pady=5, sticky="nsew")
        scroll_frame.grid_columnconfigure(0, weight=2)
        scroll_frame.grid_columnconfigure(1, weight=1)
        scroll_frame.grid_columnconfigure(2, weight=1)
        scroll_frame.grid_columnconfigure(3, weight=1)

        # Table Header
        headers = ["Platform", "Added", "Removed", "Unchanged"]
        for col_idx, h_text in enumerate(headers):
            lbl = ctk.CTkLabel(
                scroll_frame,
                text=h_text,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="gray",
            )
            lbl.grid(
                row=0,
                column=col_idx,
                padx=10,
                pady=5,
                sticky="w" if col_idx == 0 else "e",
            )

        row_idx = 1
        for p_key, pd in diff.platform_diffs.items():
            # Platform Name
            p_lbl = ctk.CTkLabel(
                scroll_frame,
                text=pd.platform_name,
                font=ctk.CTkFont(size=14, weight="bold"),
            )
            p_lbl.grid(row=row_idx, column=0, padx=10, pady=4, sticky="w")

            # Added count
            add_color = "#2ecc71" if pd.additions_count > 0 else "gray"
            add_lbl = ctk.CTkLabel(
                scroll_frame,
                text=f"+{pd.additions_count}",
                font=ctk.CTkFont(
                    size=14,
                    weight="bold" if pd.additions_count > 0 else "normal",
                ),
                text_color=add_color,
            )
            add_lbl.grid(row=row_idx, column=1, padx=10, pady=4, sticky="e")

            # Removed count
            rem_color = "#e74c3c" if pd.removals_count > 0 else "gray"
            rem_lbl = ctk.CTkLabel(
                scroll_frame,
                text=f"-{pd.removals_count}",
                font=ctk.CTkFont(
                    size=14,
                    weight="bold" if pd.removals_count > 0 else "normal",
                ),
                text_color=rem_color,
            )
            rem_lbl.grid(row=row_idx, column=2, padx=10, pady=4, sticky="e")

            # Unchanged count
            unc_lbl = ctk.CTkLabel(
                scroll_frame,
                text=f"{pd.unchanged_count}",
                font=ctk.CTkFont(size=14),
                text_color="gray",
            )
            unc_lbl.grid(row=row_idx, column=3, padx=10, pady=4, sticky="e")

            row_idx += 1

        if not diff.platform_diffs:
            empty_lbl = ctk.CTkLabel(
                scroll_frame,
                text="No enabled platform changes detected.",
                font=ctk.CTkFont(size=14),
                text_color="gray",
            )
            empty_lbl.grid(row=1, column=0, columnspan=4, pady=20)

        # Summary Bar Card
        summary_card = ctk.CTkFrame(
            self, fg_color=("gray85", "gray20"), corner_radius=8
        )
        summary_card.grid(row=3, column=0, padx=20, pady=10, sticky="ew")

        summary_text = (
            f"Total Summary:  +{diff.total_additions} to add   |   "
            f"-{diff.total_removals} to remove   |   "
            f"{diff.total_unchanged} unchanged"
        )
        summary_label = ctk.CTkLabel(
            summary_card,
            text=summary_text,
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        summary_label.pack(padx=15, pady=10)

        # Action Buttons Frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=20, pady=(5, 15))

        # 1. Continue Full Sync (Add & Remove)
        self.full_sync_btn = ctk.CTkButton(
            btn_frame,
            text="Continue Full Sync (Add & Remove)",
            command=lambda: self._select("full"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2980b9",
            hover_color="#3498db",
            height=40,
        )
        self.full_sync_btn.pack(side="left", padx=5)

        # 2. Additions Only
        self.add_only_btn = ctk.CTkButton(
            btn_frame,
            text="Perform Additions Only",
            command=lambda: self._select("add_only"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#27ae60",
            hover_color="#2ecc71",
            height=40,
        )
        self.add_only_btn.pack(side="left", padx=5)

        # 3. Cancel
        self.cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel Sync",
            command=lambda: self._select("cancel"),
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#7f8c8d",
            hover_color="#95a5a6",
            height=40,
        )
        self.cancel_btn.pack(side="left", padx=5)

        self.protocol("WM_DELETE_WINDOW", lambda: self._select("cancel"))

    def _select(self, choice: str) -> None:
        """Handle choice selection, destroy dialog, and trigger callback.

        Args:
            choice: User selection action string.
        """
        self.selected_choice = choice
        self.destroy()
        if self.on_choice:
            self.on_choice(choice)
