"""AppSettings View for managing RomM server configuration, Steam installation, and app preferences."""

import logging
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from romm_steam_sync.adapters.retroarch import (
    RetroArchFlavor,
    get_retroarch_adapter,
)
from romm_steam_sync.adapters.retroarch_launcher import (
    get_core_candidates_for_platform,
    get_default_core_for_platform,
    list_installed_cores,
)
from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.adapters.steam_guard import SteamGuard
from romm_steam_sync.adapters.steam_path import SteamPathResolver
from romm_steam_sync.adapters.steamgriddb import SteamGridDbClient
from romm_steam_sync.adapters.wrapper_installer import install_wrapper
from romm_steam_sync.config import AppSettings
from romm_steam_sync.service_layer.cleanup_service import (
    delete_all_installed_roms,
    purge_all_app_data,
)
from romm_steam_sync.service_layer.sync_service import SyncService
from romm_steam_sync.ui.components.confirmation_modal import ConfirmationModal
from romm_steam_sync.ui.components.steam_guard_modal import (
    SteamGuardModal,
    run_with_steam_guard,
)
from romm_steam_sync.ui.helpers import (
    browse_retroarch_executable,
    test_and_save_romm_credentials,
    verify_steamgriddb_key,
)
from romm_steam_sync.version import __version__

logger = logging.getLogger(__name__)


class SettingsView(ctk.CTkFrame):
    """View managing RomM server configuration, Steam profile, and application preferences."""

    def __init__(
        self,
        parent: Any,
        settings: AppSettings,
        on_connect_success: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialize SettingsView.

        Args:
            parent: Parent tkinter widget.
            settings: Active AppSettings instance.
            on_connect_success: Optional callback on successful RomM connection test.
        """
        super().__init__(parent, fg_color="transparent")
        self.settings = settings
        self.on_connect_success = on_connect_success

        self.grid_columnconfigure(0, weight=1)

        # Header Title
        title_label = ctk.CTkLabel(
            self,
            text="Settings",
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="w")

        # Version Display (Upper Right)
        self.version_label = ctk.CTkLabel(
            self,
            text=f"v{__version__}",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        self.version_label.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="e")

        subtitle_label = ctk.CTkLabel(
            self,
            text="Configure your RomM server connection, Steam installation profile, and application preferences.",
            font=ctk.CTkFont(size=16),
            text_color="gray",
        )
        subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Scrollable Settings Content Container
        scroll_content = ctk.CTkScrollableFrame(
            self,
            label_text="Configuration & Preferences",
            label_font=ctk.CTkFont(size=15, weight="bold"),
            height=460,
        )
        scroll_content.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        scroll_content.grid_columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # =========================================================================
        # 1. RomM Server Configuration Card
        # =========================================================================
        server_card = ctk.CTkFrame(scroll_content, corner_radius=10)
        server_card.grid(row=0, column=0, padx=10, pady=(10, 15), sticky="ew")
        server_card.grid_columnconfigure(1, weight=1)

        card_title = ctk.CTkLabel(
            server_card,
            text="RomM Server Configuration",
            font=ctk.CTkFont(size=17, weight="bold"),
        )
        card_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        # RomM Server URL
        url_label = ctk.CTkLabel(server_card, text="RomM Server URL:", font=ctk.CTkFont(size=14, weight="bold"))
        url_label.grid(row=1, column=0, padx=15, pady=6, sticky="w")

        self.url_entry = ctk.CTkEntry(server_card, placeholder_text="http://localhost:8080 or https://romm.example.com", font=ctk.CTkFont(size=14))
        self.url_entry.grid(row=1, column=1, padx=15, pady=6, sticky="ew")
        self.url_entry.insert(0, self.settings.romm_url)

        # API Key
        token_label = ctk.CTkLabel(server_card, text="API Key:", font=ctk.CTkFont(size=14, weight="bold"))
        token_label.grid(row=2, column=0, padx=15, pady=6, sticky="w")

        token_frame = ctk.CTkFrame(server_card, fg_color="transparent")
        token_frame.grid(row=2, column=1, padx=15, pady=6, sticky="ew")
        token_frame.grid_columnconfigure(0, weight=1)

        self.token_entry = ctk.CTkEntry(
            token_frame,
            show="*",
            placeholder_text="RomM API key / bearer token",
            font=ctk.CTkFont(size=14),
        )
        self.token_entry.grid(row=0, column=0, sticky="ew")
        self.token_entry.insert(0, self.settings.api_key)

        self.is_token_visible = False
        self.token_toggle_btn = ctk.CTkButton(
            token_frame,
            text="Show",
            width=50,
            height=34,
            fg_color="#34495e",
            hover_color="#2c3e50",
            command=self._toggle_token_visibility,
            font=ctk.CTkFont(size=13),
        )
        self.token_toggle_btn.grid(row=0, column=1, padx=(8, 0), sticky="e")

        # Server Status Feedback & Action Button
        server_action_frame = ctk.CTkFrame(server_card, fg_color="transparent")
        server_action_frame.grid(row=3, column=0, columnspan=2, padx=15, pady=(10, 15), sticky="ew")
        server_action_frame.grid_columnconfigure(0, weight=1)

        self.server_status_label = ctk.CTkLabel(
            server_action_frame,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.server_status_label.grid(row=0, column=0, sticky="w")

        self.test_server_btn = ctk.CTkButton(
            server_action_frame,
            text="Test RomM Connection & Save Server Settings",
            command=self.test_and_save_romm,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2980b9",
            hover_color="#3498db",
            height=36,
        )
        self.test_server_btn.grid(row=0, column=1, sticky="e")

        # =========================================================================
        # 2. Application Preferences & Paths Card
        # =========================================================================
        pref_card = ctk.CTkFrame(scroll_content, corner_radius=10)
        pref_card.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="ew")
        pref_card.grid_columnconfigure(1, weight=1)

        pref_title = ctk.CTkLabel(
            pref_card,
            text="Application & Steam Preferences",
            font=ctk.CTkFont(size=17, weight="bold"),
        )
        pref_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 10), sticky="w")

        # Steam User Profile Selection
        user_ids = SteamPathResolver.list_user_ids(self.settings.steam_custom_path)
        profile_options = ["auto"] + user_ids if user_ids else ["auto"]

        u_label = ctk.CTkLabel(pref_card, text="Steam User Profile:", font=ctk.CTkFont(size=14, weight="bold"))
        u_label.grid(row=1, column=0, padx=15, pady=8, sticky="w")

        self.profile_dropdown = ctk.CTkOptionMenu(
            pref_card,
            values=profile_options,
            font=ctk.CTkFont(size=14),
            dropdown_font=ctk.CTkFont(size=14),
        )
        self.profile_dropdown.grid(row=1, column=1, padx=15, pady=8, sticky="w")
        self.profile_dropdown.set(self.settings.steam_user_id)

        # Custom Steam Path
        sp_label = ctk.CTkLabel(pref_card, text="Custom Steam Path:", font=ctk.CTkFont(size=14, weight="bold"))
        sp_label.grid(row=2, column=0, padx=15, pady=8, sticky="w")

        self.steam_path_entry = ctk.CTkEntry(
            pref_card,
            placeholder_text="Auto-detected if empty",
            font=ctk.CTkFont(size=14),
        )
        self.steam_path_entry.grid(row=2, column=1, padx=15, pady=8, sticky="ew")
        self.steam_path_entry.insert(0, self.settings.steam_custom_path)

        # SteamGridDB API Key
        sgdb_label = ctk.CTkLabel(pref_card, text="SteamGridDB API Key:", font=ctk.CTkFont(size=14, weight="bold"))
        sgdb_label.grid(row=3, column=0, padx=15, pady=8, sticky="w")

        sgdb_frame = ctk.CTkFrame(pref_card, fg_color="transparent")
        sgdb_frame.grid(row=3, column=1, padx=15, pady=8, sticky="ew")
        sgdb_frame.grid_columnconfigure(0, weight=1)

        self.sgdb_entry = ctk.CTkEntry(
            sgdb_frame,
            placeholder_text="Optional API key for Heroes, Logos, Wide Grids & Icons",
            font=ctk.CTkFont(size=14),
            show="*",
        )
        self.sgdb_entry.grid(row=0, column=0, sticky="ew")
        self.sgdb_entry.insert(0, self.settings.steamgriddb_api_key)

        self.test_sgdb_btn = ctk.CTkButton(
            sgdb_frame,
            text="Test Key",
            command=self.test_sgdb_key,
            font=ctk.CTkFont(size=13),
            width=90,
        )
        self.test_sgdb_btn.grid(row=0, column=1, padx=(10, 0), sticky="e")

        # Save Syncing Toggle
        save_sync_label = ctk.CTkLabel(pref_card, text="Save Syncing:", font=ctk.CTkFont(size=14, weight="bold"))
        save_sync_label.grid(row=4, column=0, padx=15, pady=8, sticky="w")

        self.save_sync_switch = ctk.CTkSwitch(
            pref_card,
            text="Enable save file synchronization",
            font=ctk.CTkFont(size=14),
        )
        self.save_sync_switch.grid(row=4, column=1, padx=15, pady=8, sticky="w")
        if getattr(self.settings, "save_sync_enabled", True):
            self.save_sync_switch.select()
        else:
            self.save_sync_switch.deselect()

        # Default Save Slot Name
        slot_label = ctk.CTkLabel(pref_card, text="Default Save Slot:", font=ctk.CTkFont(size=14, weight="bold"))
        slot_label.grid(row=5, column=0, padx=15, pady=8, sticky="w")

        self.slot_entry = ctk.CTkEntry(
            pref_card,
            placeholder_text="Default: autosave (matches Tender & RomM clients)",
            font=ctk.CTkFont(size=14),
        )
        self.slot_entry.grid(row=5, column=1, padx=15, pady=8, sticky="ew")
        self.slot_entry.insert(0, getattr(self.settings, "default_slot", "autosave"))

        # Preferences Action Frame
        pref_action_frame = ctk.CTkFrame(pref_card, fg_color="transparent")
        pref_action_frame.grid(row=6, column=0, columnspan=2, padx=15, pady=(10, 15), sticky="ew")
        pref_action_frame.grid_columnconfigure(0, weight=1)

        self.pref_status_label = ctk.CTkLabel(
            pref_action_frame,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#2ecc71",
        )
        self.pref_status_label.grid(row=0, column=0, sticky="w")

        self.save_settings_btn = ctk.CTkButton(
            pref_action_frame,
            text="Save Preferences",
            command=self.save_preferences,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=160,
            height=36,
        )
        self.save_settings_btn.grid(row=0, column=1, sticky="e")

        # =========================================================================
        # 3. RetroArch Settings & Core Mappings Card
        # =========================================================================
        self.platform_core_widgets: Dict[str, Tuple[ctk.CTkFrame, ctk.CTkComboBox, str]] = {}

        ra_card = ctk.CTkFrame(scroll_content, corner_radius=10)
        ra_card.grid(row=2, column=0, padx=10, pady=(5, 15), sticky="ew")
        ra_card.grid_columnconfigure(1, weight=1)

        ra_title = ctk.CTkLabel(
            ra_card,
            text="RetroArch Settings & Core Mappings",
            font=ctk.CTkFont(size=17, weight="bold"),
        )
        ra_title.grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="w")

        ra_desc = ctk.CTkLabel(
            ra_card,
            text="Configure RetroArch executable path and customize libretro core mappings per platform.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        )
        ra_desc.grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="w")

        # Emulator Flavor Selection
        flavor_label = ctk.CTkLabel(ra_card, text="Emulator Flavor:", font=ctk.CTkFont(size=14, weight="bold"))
        flavor_label.grid(row=2, column=0, padx=15, pady=6, sticky="w")

        flavor_options = ["Auto-Detect", "Steam RetroArch", "Standalone RetroArch", "RetroDECK"]
        self.flavor_dropdown = ctk.CTkOptionMenu(
            ra_card,
            values=flavor_options,
            font=ctk.CTkFont(size=14),
            dropdown_font=ctk.CTkFont(size=14),
            command=self._on_flavor_changed,
        )
        self.flavor_dropdown.grid(row=2, column=1, padx=15, pady=6, sticky="w")
        current_flavor = getattr(self.settings, "emulator_flavor", "auto").lower()
        flavor_map = {
            "auto": "Auto-Detect",
            "steam": "Steam RetroArch",
            "standalone": "Standalone RetroArch",
            "retrodeck": "RetroDECK",
        }
        self.flavor_dropdown.set(flavor_map.get(current_flavor, "Auto-Detect"))

        # RetroArch Path + Browse
        ra_path_label = ctk.CTkLabel(ra_card, text="RetroArch Executable:", font=ctk.CTkFont(size=14, weight="bold"))
        ra_path_label.grid(row=3, column=0, padx=15, pady=6, sticky="w")

        ra_path_frame = ctk.CTkFrame(ra_card, fg_color="transparent")
        ra_path_frame.grid(row=3, column=1, columnspan=2, padx=15, pady=6, sticky="ew")
        ra_path_frame.grid_columnconfigure(0, weight=1)

        self.ra_entry = ctk.CTkEntry(
            ra_path_frame,
            placeholder_text="Auto-detected if empty or path to retroarch binary",
            font=ctk.CTkFont(size=14),
        )
        self.ra_entry.grid(row=0, column=0, sticky="ew")
        self.ra_entry.insert(0, self.settings.retroarch_path)

        self.ra_browse_btn = ctk.CTkButton(
            ra_path_frame,
            text="Browse...",
            width=80,
            height=34,
            command=self._browse_retroarch_path,
            font=ctk.CTkFont(size=13),
            fg_color="#34495e",
            hover_color="#2c3e50",
        )
        self.ra_browse_btn.grid(row=0, column=1, padx=(8, 0), sticky="e")

        # Core Detection Status Label
        self.core_detection_label = ctk.CTkLabel(
            ra_card,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        )
        self.core_detection_label.grid(row=4, column=1, columnspan=2, padx=15, pady=(0, 10), sticky="w")

        # Core Mappings Subheading
        cores_heading = ctk.CTkLabel(
            ra_card,
            text="Platform Core Mappings:",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        cores_heading.grid(row=5, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="w")

        # Filter & Reset All Frame
        filter_frame = ctk.CTkFrame(ra_card, fg_color="transparent")
        filter_frame.grid(row=6, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="ew")
        filter_frame.grid_columnconfigure(0, weight=1)

        self.core_filter_entry = ctk.CTkEntry(
            filter_frame,
            placeholder_text="Filter platforms by name or slug...",
            font=ctk.CTkFont(size=13),
            height=32,
        )
        self.core_filter_entry.grid(row=0, column=0, sticky="ew")
        self.core_filter_entry.bind("<KeyRelease>", lambda e: self._filter_core_rows())

        self.reset_all_cores_btn = ctk.CTkButton(
            filter_frame,
            text="Reset All to Defaults",
            command=self._reset_all_cores,
            font=ctk.CTkFont(size=12),
            fg_color="#7f8c8d",
            hover_color="#95a5a6",
            height=32,
            width=160,
        )
        self.reset_all_cores_btn.grid(row=0, column=1, padx=(10, 0), sticky="e")

        # Scrollable platform mappings container
        self.mappings_container = ctk.CTkScrollableFrame(
            ra_card,
            height=260,
            corner_radius=6,
            fg_color=("gray85", "gray17"),
        )
        self.mappings_container.grid(row=7, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="ew")
        self.mappings_container.grid_columnconfigure(0, weight=1)

        # Custom platform slug addition form
        custom_frame = ctk.CTkFrame(ra_card, fg_color="transparent")
        custom_frame.grid(row=8, column=0, columnspan=3, padx=15, pady=(5, 10), sticky="ew")
        custom_frame.grid_columnconfigure(1, weight=1)
        custom_frame.grid_columnconfigure(3, weight=1)

        custom_lbl1 = ctk.CTkLabel(custom_frame, text="Custom Slug:", font=ctk.CTkFont(size=13, weight="bold"))
        custom_lbl1.grid(row=0, column=0, padx=(0, 6), sticky="w")
        self.custom_slug_entry = ctk.CTkEntry(custom_frame, placeholder_text="e.g. atari2600", font=ctk.CTkFont(size=13), height=30)
        self.custom_slug_entry.grid(row=0, column=1, padx=(0, 10), sticky="ew")

        custom_lbl2 = ctk.CTkLabel(custom_frame, text="Core Name:", font=ctk.CTkFont(size=13, weight="bold"))
        custom_lbl2.grid(row=0, column=2, padx=(0, 6), sticky="w")
        self.custom_core_entry = ctk.CTkEntry(custom_frame, placeholder_text="e.g. stella_libretro", font=ctk.CTkFont(size=13), height=30)
        self.custom_core_entry.grid(row=0, column=3, padx=(0, 10), sticky="ew")

        self.add_custom_mapping_btn = ctk.CTkButton(
            custom_frame,
            text="Add Custom Mapping",
            command=self._add_custom_core_mapping,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#34495e",
            hover_color="#2c3e50",
            height=30,
            width=150,
        )
        self.add_custom_mapping_btn.grid(row=0, column=4, sticky="e")

        # Action & status frame for RetroArch card
        ra_action_frame = ctk.CTkFrame(ra_card, fg_color="transparent")
        ra_action_frame.grid(row=9, column=0, columnspan=3, padx=15, pady=(10, 15), sticky="ew")
        ra_action_frame.grid_columnconfigure(0, weight=1)

        self.ra_status_label = ctk.CTkLabel(
            ra_action_frame,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#2ecc71",
        )
        self.ra_status_label.grid(row=0, column=0, sticky="w")

        self.save_cores_btn = ctk.CTkButton(
            ra_action_frame,
            text="Save Core Mappings",
            command=self.save_core_mappings,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=170,
            height=36,
        )
        self.save_cores_btn.grid(row=0, column=1, sticky="e")

        self._populate_core_mappings()

        # =========================================================================
        # 4. Advanced Options Card
        # =========================================================================
        adv_card = ctk.CTkFrame(scroll_content, corner_radius=10)
        adv_card.grid(row=3, column=0, padx=10, pady=(5, 15), sticky="ew")
        adv_card.grid_columnconfigure(1, weight=1)

        adv_title = ctk.CTkLabel(
            adv_card,
            text="Advanced Options",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#e74c3c",
        )
        adv_title.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 5), sticky="w")

        adv_desc = ctk.CTkLabel(
            adv_card,
            text="Destructive storage and library management tools. Use with caution.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        )
        adv_desc.grid(row=1, column=0, columnspan=2, padx=15, pady=(0, 10), sticky="w")

        # Option 1: Delete all installed ROMs
        btn_del_roms = ctk.CTkButton(
            adv_card,
            text="Delete All Installed ROMs",
            command=self._prompt_delete_all_roms,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c0392b",
            hover_color="#e74c3c",
            height=36,
        )
        btn_del_roms.grid(row=2, column=0, padx=15, pady=8, sticky="w")

        lbl_del_roms = ctk.CTkLabel(
            adv_card,
            text="Deletes all downloaded ROM files from local library storage and resets installation DB records.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        )
        lbl_del_roms.grid(row=2, column=1, padx=15, pady=8, sticky="w")

        # Option 2: Delete RomM Steam shortcuts
        btn_del_shortcuts = ctk.CTkButton(
            adv_card,
            text="Delete RomM Steam Shortcuts",
            command=self._prompt_delete_steam_shortcuts,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c0392b",
            hover_color="#e74c3c",
            height=36,
        )
        btn_del_shortcuts.grid(row=3, column=0, padx=15, pady=8, sticky="w")

        lbl_del_shortcuts = ctk.CTkLabel(
            adv_card,
            text="Clears out all RomM shortcuts, grid artwork, and collections from Steam.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        )
        lbl_del_shortcuts.grid(row=3, column=1, padx=15, pady=8, sticky="w")

        # Option 3: Delete all romm-steam-sync data
        btn_del_all = ctk.CTkButton(
            adv_card,
            text="Delete All romm-steam-sync Data",
            command=self._prompt_delete_all_app_data,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#900C3F",
            hover_color="#C70039",
            height=36,
        )
        btn_del_all.grid(row=4, column=0, padx=15, pady=8, sticky="w")

        lbl_del_all = ctk.CTkLabel(
            adv_card,
            text="Deletes all ROMs, Steam shortcuts, save backups, database, logs, and config, then closes app.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        )
        lbl_del_all.grid(row=4, column=1, padx=15, pady=8, sticky="w")

        # Advanced Status Label
        self.advanced_status_label = ctk.CTkLabel(
            adv_card,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.advanced_status_label.grid(row=5, column=0, columnspan=2, padx=15, pady=(10, 15), sticky="w")

    def _toggle_token_visibility(self):
        self.is_token_visible = not self.is_token_visible
        if self.is_token_visible:
            self.token_entry.configure(show="")
            self.token_toggle_btn.configure(text="Hide")
        else:
            self.token_entry.configure(show="*")
            self.token_toggle_btn.configure(text="Show")

    def test_and_save_romm(self):
        """Test connection to RomM server and persist server credentials."""
        url = self.url_entry.get().strip()
        api_key = self.token_entry.get().strip()

        if not url:
            self.server_status_label.configure(text="Enter a valid RomM Server URL", text_color="#e74c3c")
            return

        self.server_status_label.configure(text="Testing connection...", text_color="#3498db")
        self.update_idletasks()

        ok, msg = test_and_save_romm_credentials(
            settings=self.settings,
            url=url,
            api_key=api_key,
            client_cls=RomMApiClient,
            install_launcher=True,
        )
        if ok:
            self.server_status_label.configure(text=msg, text_color="#2ecc71")
            if self.on_connect_success:
                self.on_connect_success()
        else:
            self.server_status_label.configure(text=msg, text_color="#e74c3c")

    def test_sgdb_key(self) -> None:
        """Test user entered SteamGridDB API key against SGDB API."""
        key = self.sgdb_entry.get().strip()
        if not key:
            self.pref_status_label.configure(
                text="Enter a SteamGridDB API key to test.",
                text_color="#e74c3c",
            )
            return

        self.pref_status_label.configure(text="Testing SteamGridDB API key...", text_color="#3498db")
        self.update_idletasks()

        ok, msg = verify_steamgriddb_key(key, client_cls=SteamGridDbClient)
        if ok:
            self.pref_status_label.configure(text=msg, text_color="#2ecc71")
        else:
            self.pref_status_label.configure(text=msg, text_color="#e74c3c")

    def _browse_retroarch_path(self) -> None:
        """Open file dialog for selecting RetroArch executable."""
        chosen = browse_retroarch_executable(parent=self)
        if chosen:
            self.ra_entry.delete(0, "end")
            self.ra_entry.insert(0, chosen)
            self.settings.retroarch_path = chosen
            self._populate_core_mappings()

    def _filter_core_rows(self) -> None:
        """Filter visible platform rows by user search query."""
        query = self.core_filter_entry.get().strip().lower()
        for slug, (row_frame, _, _) in self.platform_core_widgets.items():
            title = getattr(row_frame, "_platform_title", slug.lower())
            if not query or query in title:
                row_frame.pack(fill="x", padx=4, pady=3)
            else:
                row_frame.pack_forget()

    def _reset_core(self, slug: str) -> None:
        """Reset a single platform core mapping to default."""
        if slug in self.platform_core_widgets:
            _, combo, default_core = self.platform_core_widgets[slug]
            combo.set(f"{default_core} [Default]" if default_core else "")
            self.settings.remove_core_override(slug)
            if hasattr(self, "ra_status_label"):
                self.ra_status_label.configure(
                    text=f"Reset '{slug}' to default core ({default_core}). Click Save to persist.",
                    text_color="#f39c12",
                )

    def _reset_all_cores(self) -> None:
        """Reset all platform core mappings to their respective defaults."""
        for slug, (_, combo, default_core) in self.platform_core_widgets.items():
            combo.set(f"{default_core} [Default]" if default_core else "")
        self.settings.clear_all_core_overrides()
        if hasattr(self, "ra_status_label"):
            self.ra_status_label.configure(
                text="All cores reset to defaults. Click Save Core Mappings to persist.",
                text_color="#f39c12",
            )

    def _add_custom_core_mapping(self) -> None:
        """Add a custom platform slug to core mapping row."""
        slug = self.custom_slug_entry.get().strip().lower()
        core = self.custom_core_entry.get().strip()
        if not slug or not core:
            if hasattr(self, "ra_status_label"):
                self.ra_status_label.configure(
                    text="Please enter both Custom Slug and Core Name.",
                    text_color="#e74c3c",
                )
            return

        self.settings.set_core_override(slug, core)
        self.custom_slug_entry.delete(0, "end")
        self.custom_core_entry.delete(0, "end")
        self._populate_core_mappings()
        if hasattr(self, "ra_status_label"):
            self.ra_status_label.configure(
                text=f"Added custom override for '{slug}' -> '{core}'. Click Save to persist.",
                text_color="#2ecc71",
            )

    def _on_flavor_changed(self, choice: str) -> None:
        """Handle user selection of emulator flavor."""
        val_map = {
            "Auto-Detect": "auto",
            "Steam RetroArch": "steam",
            "Standalone RetroArch": "standalone",
            "RetroDECK": "retrodeck",
        }
        self.settings.emulator_flavor = val_map.get(choice, "auto")
        self._populate_core_mappings()

    def _populate_core_mappings(self) -> None:
        """Populate platform core mapping rows in the scrollable container."""
        for child in self.mappings_container.winfo_children():
            child.destroy()

        self.platform_core_widgets.clear()

        ra_path = self.ra_entry.get().strip()
        flavor = getattr(self.settings, "emulator_flavor", "auto")
        adapter = get_retroarch_adapter(ra_path, flavor=flavor)
        installed_cores = adapter.list_installed_cores()
        flavor_name = adapter.flavor.name.title()
        if adapter.flavor.name == "STEAM":
            flavor_name = "Steam RetroArch"
        elif adapter.flavor.name == "STANDALONE":
            flavor_name = "Standalone RetroArch"
        elif adapter.flavor.name == "RETRODECK":
            flavor_name = "RetroDECK"

        if installed_cores:
            self.core_detection_label.configure(
                text=f"Detected flavor: {flavor_name} | {len(installed_cores)} installed libretro core(s) in RetroArch path.",
                text_color="#2ecc71",
            )
        else:
            self.core_detection_label.configure(
                text=f"Detected flavor: {flavor_name} | No installed cores detected in search directories. Defaults will be used.",
                text_color="gray",
            )

        canonical_map: Dict[str, str] = {
            "snes": "Super Nintendo (SNES) / Super Famicom",
            "nes": "Nintendo Entertainment System (NES) / Famicom",
            "n64": "Nintendo 64 (N64)",
            "gba": "Game Boy Advance (GBA)",
            "gb": "Game Boy",
            "gbc": "Game Boy Color",
            "nds": "Nintendo DS (NDS)",
            "3ds": "Nintendo 3DS",
            "gc": "Nintendo GameCube",
            "wii": "Nintendo Wii",
            "wiiu": "Nintendo Wii U",
            "genesis": "Sega Genesis / Mega Drive",
            "sms": "Sega Master System (SMS)",
            "gamegear": "Sega Game Gear",
            "segacd": "Sega CD / Mega-CD",
            "sega32x": "Sega 32X",
            "saturn": "Sega Saturn",
            "dc": "Sega Dreamcast",
            "ps1": "PlayStation (PS1 / PSX)",
            "ps2": "PlayStation 2 (PS2)",
            "psp": "PlayStation Portable (PSP)",
            "ps3": "PlayStation 3 (PS3)",
            "psvita": "PlayStation Vita",
            "pce": "PC Engine / TurboGrafx-16",
            "3do": "3DO Interactive Multiplayer",
            "neogeo": "Neo Geo",
        }

        all_slugs = list(canonical_map.keys())
        for extra in list(self.settings.core_mappings.keys()) + list(
            self.settings.enabled_platforms
        ):
            s = extra.lower().strip()
            if s and s not in all_slugs:
                all_slugs.append(s)

        for slug in all_slugs:
            display_title = canonical_map.get(slug, slug.upper())
            default_core = adapter.get_default_core_for_platform(slug) or ""
            current_override = self.settings.get_core_override(slug)
            active_value = current_override or default_core

            candidates = adapter.get_core_candidates_for_platform(slug)
            option_set: List[str] = []
            if default_core:
                option_set.append(f"{default_core} [Default]")
            for c in candidates:
                if c != default_core and c not in option_set:
                    option_set.append(c)
            for ic in installed_cores:
                if ic != default_core and ic not in option_set:
                    option_set.append(f"{ic} [Installed]")

            row_frame = ctk.CTkFrame(self.mappings_container, fg_color="transparent")
            row_frame.pack(fill="x", padx=4, pady=3)
            row_frame._platform_title = f"{display_title} {slug}".lower()  # type: ignore
            row_frame.grid_columnconfigure(0, weight=1)

            lbl = ctk.CTkLabel(
                row_frame,
                text=f"{display_title} ({slug})",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            )
            lbl.grid(row=0, column=0, padx=(8, 10), pady=4, sticky="w")

            combo_values = (
                option_set
                if option_set
                else ([active_value] if active_value else ["None"])
            )
            combo = ctk.CTkComboBox(
                row_frame,
                values=combo_values,
                width=240,
                font=ctk.CTkFont(size=13),
                dropdown_font=ctk.CTkFont(size=13),
            )
            combo.grid(row=0, column=1, padx=6, pady=4, sticky="e")
            if current_override:
                combo.set(current_override)
            else:
                combo.set(f"{default_core} [Default]" if default_core else "")

            reset_btn = ctk.CTkButton(
                row_frame,
                text="Reset",
                width=60,
                height=28,
                font=ctk.CTkFont(size=12),
                fg_color="#34495e",
                hover_color="#2c3e50",
                command=lambda s=slug: self._reset_core(s),
            )
            reset_btn.grid(row=0, column=2, padx=(6, 8), pady=4, sticky="e")

            self.platform_core_widgets[slug] = (row_frame, combo, default_core)

    def save_core_mappings(self) -> None:
        """Save core mappings and RetroArch executable path to settings."""
        logger.info("Saving RetroArch core mapping overrides...")
        self.settings.retroarch_path = self.ra_entry.get().strip()

        if hasattr(self, "flavor_dropdown"):
            choice = self.flavor_dropdown.get()
            val_map = {
                "Auto-Detect": "auto",
                "Steam RetroArch": "steam",
                "Standalone RetroArch": "standalone",
                "RetroDECK": "retrodeck",
            }
            self.settings.emulator_flavor = val_map.get(choice, "auto")

        for slug, (_, combo, default_core) in self.platform_core_widgets.items():
            val = combo.get().strip()
            if val.endswith(" [Default]"):
                val = val[: -len(" [Default]")].strip()
            elif val.endswith(" [Installed]"):
                val = val[: -len(" [Installed]")].strip()

            if val and val != default_core:
                self.settings.set_core_override(slug, val)
            else:
                self.settings.remove_core_override(slug)

        self.settings.save()
        logger.info(
            "Saved %d custom core mappings to settings.json",
            len(self.settings.core_mappings),
        )
        if hasattr(self, "ra_status_label"):
            count = len(self.settings.core_mappings)
            self.ra_status_label.configure(
                text=f"Core mappings saved ({count} custom override{'s' if count != 1 else ''} active).",
                text_color="#2ecc71",
            )

    def save_preferences(self) -> None:
        """Persist user modified application preferences to settings store."""
        logger.info("Saving application settings preferences...")
        self.settings.steam_user_id = self.profile_dropdown.get()
        self.settings.steam_custom_path = self.steam_path_entry.get().strip()
        self.settings.retroarch_path = self.ra_entry.get().strip()
        self.settings.steamgriddb_api_key = self.sgdb_entry.get().strip()
        self.settings.default_slot = (
            self.slot_entry.get().strip() or "autosave"
        )
        self.settings.save_sync_enabled = bool(self.save_sync_switch.get())
        self.save_core_mappings()
        self.settings.save()
        logger.info("Application settings saved successfully.")
        self.pref_status_label.configure(
            text="Preferences saved successfully!", text_color="#2ecc71"
        )

    # =========================================================================
    # Advanced Options Prompt Handlers & Actions
    # =========================================================================
    def _prompt_delete_all_roms(self):
        """Show confirmation dialog to delete all locally installed ROM files."""
        ConfirmationModal(
            self.winfo_toplevel(),
            window_title="Confirm ROM Deletion",
            header_title="Delete All Installed ROMs",
            message=(
                "Are you sure you want to delete all installed ROMs?\n\n"
                "This action will permanently delete all downloaded ROM files from\n"
                "your local library storage and clear installation records in the DB.\n"
                "Remote ROM files on your RomM server will NOT be deleted."
            ),
            confirm_text="Delete ROMs",
            confirm_color="#c0392b",
            confirm_hover="#e74c3c",
            on_confirm=self._execute_delete_all_roms,
            width=520,
            height=240,
        )

    def _execute_delete_all_roms(self):
        logger.info("User confirmed deletion of all installed ROMs.")
        ok, msg, count = delete_all_installed_roms(self.settings)
        if ok:
            self.advanced_status_label.configure(text=msg, text_color="#2ecc71")
        else:
            self.advanced_status_label.configure(text=msg, text_color="#e74c3c")

    def _prompt_delete_steam_shortcuts(self):
        """Show confirmation dialog to delete all RomM Steam shortcuts and collections."""
        ConfirmationModal(
            self.winfo_toplevel(),
            window_title="Confirm Steam Shortcut Cleanup",
            header_title="Delete RomM Steam Shortcuts",
            message=(
                "Are you sure you want to delete all RomM Steam shortcuts?\n\n"
                "This will clear out all shortcuts, grid artwork files, and Steam\n"
                "collections generated by romm-steam-sync. A pre-cleanup Steam\n"
                "backup will be created. Please ensure Steam is closed before proceeding."
            ),
            confirm_text="Delete Shortcuts",
            confirm_color="#c0392b",
            confirm_hover="#e74c3c",
            on_confirm=self._check_and_execute_delete_steam_shortcuts,
            width=520,
            height=240,
        )

    def _check_and_execute_delete_steam_shortcuts(self):
        run_with_steam_guard(self.winfo_toplevel(), on_proceed=self._execute_delete_steam_shortcuts)

    def _execute_delete_steam_shortcuts(self):
        logger.info("Executing deletion of all RomM Steam shortcuts...")
        try:
            sync_service = SyncService(settings=self.settings)
            ok, msg, count = sync_service.remove_all_synced_libraries(skip_steam_guard=True)
            if ok:
                self.advanced_status_label.configure(
                    text=f"{msg} Safe to reopen Steam.",
                    text_color="#2ecc71",
                )
            else:
                self.advanced_status_label.configure(text=msg, text_color="#e74c3c")
        except Exception as e:
            logger.error("Failed deleting RomM Steam shortcuts: %s", e, exc_info=True)
            self.advanced_status_label.configure(text=f"Failed: {str(e)}", text_color="#e74c3c")

    def _prompt_delete_all_app_data(self):
        """Show confirmation dialog to purge all application data and close app."""
        ConfirmationModal(
            self.winfo_toplevel(),
            window_title="Confirm Full App Data Purge",
            header_title="Delete All romm-steam-sync Data",
            message=(
                "WARNING: This action will permanently delete ALL app data:\n"
                "• All downloaded ROMs from local library storage\n"
                "• All RomM Steam shortcuts, grid artwork & Steam collections\n"
                "• All save file backups and shared memory card files\n"
                "• All application database records, logs, and settings\n\n"
                "The application will automatically close upon completion.\n"
                "Relaunching the app will re-initialize setup from scratch."
            ),
            confirm_text="Purge All Data & Close",
            confirm_color="#900C3F",
            confirm_hover="#C70039",
            on_confirm=self._check_and_execute_delete_all_app_data,
            width=540,
            height=280,
        )

    def _check_and_execute_delete_all_app_data(self):
        run_with_steam_guard(self.winfo_toplevel(), on_proceed=self._execute_delete_all_app_data)

    def _execute_delete_all_app_data(self):
        logger.info("Executing purge of all romm-steam-sync application data...")
        ok, msg = purge_all_app_data(settings=self.settings, skip_steam_guard=True)
        if ok:
            logger.info("App data purge finished. Closing application now.")
            try:
                top = self.winfo_toplevel()
                top.destroy()
            except Exception as e:
                logger.warning("Failed destroying main window during app exit: %s", e)
            sys.exit(0)
        else:
            self.advanced_status_label.configure(text=msg, text_color="#e74c3c")
