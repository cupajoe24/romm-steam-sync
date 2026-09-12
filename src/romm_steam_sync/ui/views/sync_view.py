"""Library Sync Execution View."""

import logging
import threading
from typing import Any, Optional

import customtkinter as ctk

from romm_steam_sync.adapters.steam_guard import SteamGuard
from romm_steam_sync.config import AppSettings
from romm_steam_sync.domain.sync_diff import SyncDiff
from romm_steam_sync.service_layer.sync_service import (
    SteamRunningException,
    SyncService,
)
from romm_steam_sync.ui.components.cancel_modal import SyncCancelModal
from romm_steam_sync.ui.components.cover_conveyor import RomCoverConveyor
from romm_steam_sync.ui.components.steam_guard_modal import (
    SteamGuardModal,
    run_with_steam_guard,
    show_sync_complete_modal,
)
from romm_steam_sync.ui.components.sync_diff_modal import SyncDiffModal
from romm_steam_sync.ui.components.timeout_modal import RomMTimeoutModal
from romm_steam_sync.ui.helpers import (
    prompt_timeout_dialog,
    reset_progress_bar,
    update_sync_progress_ui,
)

logger = logging.getLogger(__name__)


class SyncView(ctk.CTkFrame):
    """View executing library sync to Steam with progress reporting and animated ROM cover conveyor."""

    def __init__(self, parent: Any, settings: AppSettings) -> None:
        """Initialize SyncView.

        Args:
            parent: Parent tkinter widget.
            settings: Application settings instance.
        """
        super().__init__(parent, fg_color="transparent")
        self.settings = settings
        self.sync_service = SyncService(settings=settings)
        self._cancellation_requested: Optional[str] = None

        self.grid_columnconfigure(0, weight=1)

        # Header Title
        title_label = ctk.CTkLabel(
            self,
            text="Library Synchronization",
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        subtitle_label = ctk.CTkLabel(
            self,
            text="Sync games from your enabled RomM platforms into Steam. Steam must remain closed during this process.",
            font=ctk.CTkFont(size=16),
            text_color="gray",
        )
        subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Sync Action Bar
        action_card = ctk.CTkFrame(self, corner_radius=10)
        action_card.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        action_card.grid_columnconfigure(0, weight=1)

        # Action Buttons Layout (Start Sync & Cancel Sync)
        btn_bar = ctk.CTkFrame(action_card, fg_color="transparent")
        btn_bar.grid(row=0, column=0, padx=20, pady=15, sticky="ew")
        btn_bar.grid_columnconfigure(0, weight=3)
        btn_bar.grid_columnconfigure(1, weight=1)

        self.start_btn = ctk.CTkButton(
            btn_bar,
            text="Start Library Sync to Steam",
            command=self.start_sync_flow,
            font=ctk.CTkFont(size=18, weight="bold"),
            height=45,
            fg_color="#2980b9",
            hover_color="#3498db",
        )
        self.start_btn.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.cancel_btn = ctk.CTkButton(
            btn_bar,
            text="Cancel Sync",
            command=self.on_cancel_clicked,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=45,
            fg_color="#e74c3c",
            hover_color="#c0392b",
            state="disabled",
        )
        self.cancel_btn.grid(row=0, column=1, sticky="ew")

        # Progress Bar & Percentage
        self.progress_bar = ctk.CTkProgressBar(action_card)
        self.progress_bar.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        self.progress_bar.set(0.0)

        self.status_lbl = ctk.CTkLabel(
            action_card,
            text="Ready to sync.",
            font=ctk.CTkFont(size=15),
        )
        self.status_lbl.grid(row=2, column=0, padx=20, pady=(0, 15))

        # Animated ROM Cover Conveyor Component
        self.cover_conveyor = RomCoverConveyor(self)
        self.cover_conveyor.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="nsew")
        self.rowconfigure(3, weight=1)

    def append_log(self, text: str) -> None:
        """Append log message to the animated conveyor log viewer.

        Args:
            text: Log message string to display.
        """
        self.cover_conveyor.append_log(text)

    def start_sync_flow(self) -> None:
        """Initiate sync flow with Steam Safety Guard check."""
        logger.info("User initiated library sync flow...")
        top = self.winfo_toplevel() if hasattr(self, "winfo_toplevel") else self
        run_with_steam_guard(top, on_proceed=self._run_sync_thread)

    def on_cancel_clicked(self) -> None:
        """Open cancel modal dialog to prompt user for Cancel or Rollback choice."""
        logger.info("User clicked Cancel Sync button.")
        top = self.winfo_toplevel() if hasattr(self, "winfo_toplevel") else self
        SyncCancelModal(top, on_choice=self._handle_cancel_choice)

    def _handle_cancel_choice(self, choice: str) -> None:
        """Handle user choice from SyncCancelModal.

        Args:
            choice: User selection ('cancel' or 'rollback').
        """
        logger.info("User selected cancel modal choice: %s", choice)
        if choice in ("cancel", "rollback"):
            self._cancellation_requested = choice
            self.status_lbl.configure(text=f"Cancelling sync pass ({choice})...")

    def _run_sync_thread(self) -> None:
        """Prepare UI controls and launch background sync execution thread."""
        self.start_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        reset_progress_bar(self.progress_bar, mode="determinate", value=0.0)
        self.status_lbl.configure(text="Starting library synchronization pass...", text_color="#ecf0f1")
        self._cancellation_requested = None
        self.cover_conveyor.clear()
        self.append_log("Starting library synchronization pass...")

        thread = threading.Thread(target=self._execute_sync_worker, daemon=True)
        thread.start()

    def _prompt_user_on_diff(self, diff: SyncDiff) -> str:
        """Thread-safe invocation of SyncDiffModal on GUI thread.

        Args:
            diff: SyncDiff calculation result.

        Returns:
            User resolution choice string ('apply' or 'cancel').
        """
        logger.info(
            "Displaying sync diff modal to user (+%d, -%d, %d unchanged)...",
            diff.total_additions,
            diff.total_removals,
            diff.total_unchanged,
        )
        result_container = {"choice": "cancel"}
        done_event = threading.Event()

        def _show_modal() -> None:
            reset_progress_bar(self.progress_bar, mode="determinate", value=0.38)

            def _handle_choice(choice: str) -> None:
                result_container["choice"] = choice
                done_event.set()

            top = self.winfo_toplevel() if hasattr(self, "winfo_toplevel") else self
            SyncDiffModal(
                top,
                diff=diff,
                on_choice=_handle_choice,
            )

        self.after(0, _show_modal)
        done_event.wait()
        logger.info("User selected diff resolution choice: %s", result_container["choice"])
        return result_container["choice"]

    def _prompt_user_on_timeout(self, platform_name: str, backup_id: Optional[str]) -> str:
        """Thread-safe invocation of RomMTimeoutModal on GUI thread.

        Args:
            platform_name: Name of platform encountering timeout.
            backup_id: Optional pre-sync Steam backup ID.

        Returns:
            User resolution choice string.
        """
        return prompt_timeout_dialog(self, self.progress_bar, platform_name, backup_id)

    def _execute_sync_worker(self) -> None:
        """Worker thread executing library synchronization pass."""
        def progress_cb(
            pct: float,
            msg: str,
            cover_path: Optional[str] = None,
            rom_name: Optional[str] = None,
        ) -> None:
            self.after(
                0, lambda: self._update_ui_progress(pct, msg, cover_path, rom_name)
            )

        try:
            success, message, count = self.sync_service.sync_library(
                progress_callback=progress_cb,
                skip_steam_guard=True,
                on_timeout_callback=self._prompt_user_on_timeout,
                is_cancelled_callback=lambda: self._cancellation_requested,
                on_diff_callback=self._prompt_user_on_diff,
            )
            self.after(0, lambda: self._on_sync_finished(success, message, count))
        except SteamRunningException as e:
            logger.error("Sync worker stopped due to running Steam process: %s", e)
            self.after(0, lambda: self._on_sync_finished(False, str(e), 0))
        except Exception as e:
            logger.error("Sync worker encountered unexpected exception: %s", e, exc_info=True)
            self.after(0, lambda: self._on_sync_finished(False, f"Unexpected error: {e}", 0))

    def _update_ui_progress(
        self,
        pct: float,
        msg: str,
        cover_path: Optional[str] = None,
        rom_name: Optional[str] = None,
    ) -> None:
        """Update progress bar, status label, and animated conveyor on the UI.

        Args:
            pct: Progress fraction from 0.0 to 1.0 (or negative for indeterminate).
            msg: Status message to display.
            cover_path: Optional artwork path.
            rom_name: Optional ROM title.
        """
        update_sync_progress_ui(
            progress_bar=self.progress_bar,
            status_lbl=self.status_lbl,
            conveyor=self.cover_conveyor,
            pct=pct,
            msg=msg,
            cover_path=cover_path,
            rom_name=rom_name,
            append_log_cb=self.append_log,
        )

    def _on_sync_finished(self, success: bool, message: str, count: int) -> None:
        """Handle completion or failure of the sync worker thread.

        Args:
            success: True if sync finished successfully.
            message: Result or error message string.
            count: Number of synced games.
        """
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        reset_progress_bar(self.progress_bar, mode="determinate")

        if success:
            logger.info("Sync finished successfully: %s (%d items)", message, count)
            self.progress_bar.set(1.0)
            self.status_lbl.configure(text=message, text_color="#2ecc71")
            self.append_log(f"SUCCESS: {message}")
            top = self.winfo_toplevel() if hasattr(self, "winfo_toplevel") else self
            show_sync_complete_modal(top)
        else:
            logger.warning("Sync finished or stopped: %s", message)
            self.status_lbl.configure(
                text=message,
                text_color="#e67e22" if "cancelled" in message.lower() else "#e74c3c",
            )
            self.append_log(f"STATUS: {message}")
