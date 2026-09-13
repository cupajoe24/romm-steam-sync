"""Cleanup & Restore Manager View for removing synced libraries and rolling back backups."""

import logging
from typing import Any, Dict, List, Optional

import customtkinter as ctk

from romm_steam_sync.adapters.steam_backup import SteamBackupManager
from romm_steam_sync.adapters.steam_guard import SteamGuard
from romm_steam_sync.adapters.steam_path import SteamPathResolver
from romm_steam_sync.config import AppSettings
from romm_steam_sync.service_layer.sync_service import (
    SteamRunningException,
    SyncService,
)
from romm_steam_sync.ui.components.confirmation_modal import (
    AlertModal,
    ConfirmationModal,
)
from romm_steam_sync.ui.components.steam_guard_modal import (
    SteamGuardModal,
    run_with_steam_guard,
)

logger = logging.getLogger(__name__)


class CleanupRestoreView(ctk.CTkFrame):
    """View managing library cleanups (reverse sync) and Steam VDF backup restores."""

    def __init__(self, parent: Any, settings: AppSettings) -> None:
        """Initialize CleanupRestoreView.

        Args:
            parent: Parent tkinter widget.
            settings: Application settings instance.
        """
        super().__init__(parent, fg_color="transparent")
        self.settings = settings
        self.backup_mgr = SteamBackupManager()
        self.sync_service = SyncService(settings=settings)

        self.grid_columnconfigure(0, weight=1)

        # Header Title
        title_label = ctk.CTkLabel(
            self,
            text="Cleanup & Restore",
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        subtitle_label = ctk.CTkLabel(
            self,
            text="Remove synced Steam collections and shortcuts, or roll back to prior Steam VDF backups.",
            font=ctk.CTkFont(size=16),
            text_color="gray",
        )
        subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Scrollable Main Content Container
        scroll_content = ctk.CTkScrollableFrame(
            self,
            label_text="Library Cleanup & Restore Operations",
            label_font=ctk.CTkFont(size=15, weight="bold"),
            height=440,
        )
        scroll_content.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        scroll_content.grid_columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # -------------------------------------------------------------
        # Section 1: Library Cleanup (Reverse Sync)
        # -------------------------------------------------------------
        c_header = ctk.CTkLabel(
            scroll_content,
            text="Remove Synced Steam Libraries",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        c_header.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="w")

        c_desc = ctk.CTkLabel(
            scroll_content,
            text="Delete shortcuts, grid artwork, and Steam collection categories for synced libraries.",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        c_desc.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="w")

        cleanup_controls_frame = ctk.CTkFrame(scroll_content, fg_color="transparent")
        cleanup_controls_frame.grid(row=2, column=0, padx=15, pady=5, sticky="ew")
        cleanup_controls_frame.grid_columnconfigure(1, weight=1)

        lib_label = ctk.CTkLabel(cleanup_controls_frame, text="Select Library:", font=ctk.CTkFont(size=15, weight="bold"))
        lib_label.grid(row=0, column=0, padx=(0, 10), pady=10, sticky="w")

        self.library_dropdown = ctk.CTkOptionMenu(
            cleanup_controls_frame,
            values=["Loading..."],
            font=ctk.CTkFont(size=15),
            dropdown_font=ctk.CTkFont(size=15),
            width=280,
        )
        self.library_dropdown.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        refresh_btn = ctk.CTkButton(
            cleanup_controls_frame,
            text="Refresh",
            command=self.refresh,
            font=ctk.CTkFont(size=14),
            width=100,
        )
        refresh_btn.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        # Action Buttons
        btn_frame = ctk.CTkFrame(scroll_content, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=15, pady=10, sticky="w")

        self.remove_selected_btn = ctk.CTkButton(
            btn_frame,
            text="Remove Selected Library",
            command=self.prompt_remove_selected,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#d35400",
            hover_color="#e67e22",
            width=220,
        )
        self.remove_selected_btn.pack(side="left", padx=(0, 15))

        self.remove_all_btn = ctk.CTkButton(
            btn_frame,
            text="Remove All Libraries",
            command=self.prompt_remove_all,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c0392b",
            hover_color="#e74c3c",
            width=200,
        )
        self.remove_all_btn.pack(side="left")

        # Status Message
        self.cleanup_status_label = ctk.CTkLabel(
            scroll_content,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.cleanup_status_label.grid(row=4, column=0, padx=15, pady=5, sticky="w")

        # -------------------------------------------------------------
        # Section 2: Backup & Rollback Section
        # -------------------------------------------------------------
        divider = ctk.CTkFrame(scroll_content, height=2, fg_color="gray")
        divider.grid(row=5, column=0, padx=15, pady=20, sticky="ew")

        b_header = ctk.CTkLabel(
            scroll_content,
            text="Steam VDF Backups & Rollback (Max 5 Retained)",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        b_header.grid(row=6, column=0, padx=15, pady=(5, 10), sticky="w")

        self.backups_list_frame = ctk.CTkFrame(scroll_content, fg_color="transparent")
        self.backups_list_frame.grid(row=7, column=0, padx=15, pady=5, sticky="ew")

        # Load data
        self.refresh()

    def refresh(self) -> None:
        """Refresh synced libraries and backups list."""
        logger.debug("Refreshing CleanupRestoreView data...")
        self.refresh_synced_libraries()
        self.refresh_backups_list()

    def refresh_synced_libraries(self) -> None:
        """Fetch synced collections and update option menu."""
        libs = self.sync_service.get_synced_libraries()
        self.synced_libs_cache = libs
        if not libs:
            self.library_dropdown.configure(values=["No synced libraries found"])
            self.library_dropdown.set("No synced libraries found")
            self.remove_selected_btn.configure(state="disabled")
            self.remove_all_btn.configure(state="disabled")
            return

        options = [f"{lib['name']} ({lib['count']} games)" for lib in libs]
        self.library_dropdown.configure(values=options)
        self.library_dropdown.set(options[0])
        self.remove_selected_btn.configure(state="normal")
        self.remove_all_btn.configure(state="normal")

    def refresh_backups_list(self):
        """Populate list of up to 5 available backups with restore buttons."""
        for widget in self.backups_list_frame.winfo_children():
            widget.destroy()

        backups = self.backup_mgr.list_backups()

        if not backups:
            lbl = ctk.CTkLabel(
                self.backups_list_frame,
                text="No backups created yet.",
                font=ctk.CTkFont(size=15),
                text_color="gray",
            )
            lbl.pack(pady=10)
            return

        for b in backups:
            row_frame = ctk.CTkFrame(self.backups_list_frame, corner_radius=6)
            row_frame.pack(fill="x", pady=4)

            b_info = ctk.CTkLabel(
                row_frame,
                text=f"{b['id']}  ({b['created_at']})",
                font=ctk.CTkFont(size=15, weight="bold"),
            )
            b_info.pack(side="left", padx=15, pady=8)

            restore_btn = ctk.CTkButton(
                row_frame,
                text="Rollback",
                command=lambda b_id=b["id"]: self.restore_selected_backup(b_id),
                font=ctk.CTkFont(size=15),
                width=100,
                fg_color="#c0392b",
                hover_color="#e74c3c",
            )
            restore_btn.pack(side="right", padx=15, pady=8)

    # -------------------------------------------------------------
    # Action Handlers: Remove Selected & Remove All
    # -------------------------------------------------------------
    def prompt_remove_selected(self) -> None:
        """Show confirmation dialog to remove currently selected library collection."""
        selected_text = self.library_dropdown.get()
        if not selected_text or "No synced" in selected_text:
            return

        lib_name = selected_text.split(" (")[0]
        ConfirmationModal(
            self.winfo_toplevel(),
            window_title="Confirm Library Removal",
            header_title="Confirm Library Cleanup",
            message=(
                f"Are you sure you want to remove '{lib_name}'?\n\n"
                f"This will remove all shortcuts, grid artwork, and delete the\n"
                f"'{lib_name}' Steam collection. A pre-cleanup backup will be created."
            ),
            confirm_text="Remove Library",
            header_color="#e67e22",
            confirm_color="#d35400",
            confirm_hover="#e67e22",
            on_confirm=lambda: self._execute_remove_selected(lib_name),
            width=480,
            height=230,
        )

    def _execute_remove_selected(self, lib_name: str):
        run_with_steam_guard(
            self.winfo_toplevel(),
            on_proceed=lambda: self._do_remove_selected(lib_name, skip_guard=True),
        )

    def _do_remove_selected(self, lib_name: str, skip_guard: bool):
        logger.info("Executing removal of selected library: %s", lib_name)
        try:
            ok, msg, count = self.sync_service.remove_synced_library(lib_name, skip_steam_guard=skip_guard)
            if ok:
                logger.info("Removed library '%s' (%d items): %s", lib_name, count, msg)
                self.cleanup_status_label.configure(text=msg, text_color="#2ecc71")
                self.refresh()
            else:
                logger.error("Failed to remove library '%s': %s", lib_name, msg)
                self.cleanup_status_label.configure(text=msg, text_color="#e74c3c")
        except SteamRunningException as e:
            logger.warning("Removal of library '%s' blocked: %s", lib_name, e)
            self.cleanup_status_label.configure(text=str(e), text_color="#e67e22")

    def prompt_remove_all(self) -> None:
        """Show confirmation dialog to purge all synced RomM shortcuts and collections."""
        ConfirmationModal(
            self.winfo_toplevel(),
            window_title="Confirm Remove All Libraries",
            header_title="Remove ALL Synced Libraries",
            message=(
                "Are you sure you want to remove ALL RomM synced games?\n\n"
                "This will remove all RomM shortcuts, grid artwork, and all\n"
                "RomM Steam collections. A pre-cleanup backup will be created."
            ),
            confirm_text="Remove ALL Libraries",
            header_color="#e74c3c",
            confirm_color="#c0392b",
            confirm_hover="#e74c3c",
            on_confirm=self._execute_remove_all,
            width=500,
            height=240,
        )

    def _execute_remove_all(self):
        run_with_steam_guard(
            self.winfo_toplevel(),
            on_proceed=lambda: self._do_remove_all(skip_guard=True),
        )

    def _do_remove_all(self, skip_guard: bool):
        logger.info("Executing removal of ALL synced libraries...")
        try:
            ok, msg, count = self.sync_service.remove_all_synced_libraries(skip_steam_guard=skip_guard)
            if ok:
                logger.info("Removed ALL synced libraries (%d items total): %s", count, msg)
                self.cleanup_status_label.configure(text=msg, text_color="#2ecc71")
                self.refresh()
            else:
                logger.error("Failed to remove all synced libraries: %s", msg)
                self.cleanup_status_label.configure(text=msg, text_color="#e74c3c")
        except SteamRunningException as e:
            logger.warning("Removal of all libraries blocked: %s", e)
            self.cleanup_status_label.configure(text=str(e), text_color="#e67e22")

    # -------------------------------------------------------------
    # Rollback Backup Handler
    # -------------------------------------------------------------
    def restore_selected_backup(self, backup_id: str) -> None:
        """Initiate rollback to a specific Steam VDF backup snapshot.

        Args:
            backup_id: Identifier of the backup snapshot to restore.
        """
        run_with_steam_guard(
            self.winfo_toplevel(),
            on_proceed=lambda: self._do_restore(backup_id),
        )

    def _do_restore(self, backup_id: str):
        logger.info("Executing restore of backup: %s", backup_id)
        config_dir, _ = SteamPathResolver.get_user_config_dir(
            user_id=self.settings.steam_user_id,
            custom_steam_path=self.settings.steam_custom_path,
        )
        if not config_dir:
            logger.error("Cannot restore backup %s: Steam config directory not found.", backup_id)
            return

        ok = self.backup_mgr.restore_backup(backup_id, str(config_dir))
        if ok:
            logger.info("Successfully restored backup %s to %s", backup_id, config_dir)
            self.refresh()
            self._show_rollback_success_modal(backup_id)
        else:
            logger.error("Failed to restore backup %s to %s", backup_id, config_dir)

    def _show_rollback_success_modal(self, backup_id: str):
        AlertModal(
            self.winfo_toplevel(),
            window_title="Rollback Successful",
            header_title="Rollback Successful!",
            message=(
                f"Restored Steam shortcuts and collections from:\n{backup_id}\n\n"
                f"Please launch or restart Steam to view the restored state."
            ),
            button_text="OK",
            header_color="#2ecc71",
            width=480,
            height=230,
        )
