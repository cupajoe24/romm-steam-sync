"""Onboarding Wizard View for first-time application setup."""

import logging
import os
from pathlib import Path
import sys
import threading
from typing import Any, Callable, Dict, List, Optional
import webbrowser

import customtkinter as ctk

from romm_steam_sync.adapters.retroarch import (
    RetroArchFlavor,
    get_retroarch_adapter,
)
from romm_steam_sync.adapters.retroarch_launcher import RetroArchLauncher
from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.adapters.steam_guard import SteamGuard
from romm_steam_sync.adapters.steamgriddb import SteamGridDbClient
from romm_steam_sync.config import AppSettings
from romm_steam_sync.service_layer.sync_service import (
    SteamRunningException,
    SyncService,
)
from romm_steam_sync.ui.components.cancel_modal import SyncCancelModal
from romm_steam_sync.ui.components.cover_conveyor import RomCoverConveyor
from romm_steam_sync.ui.components.platform_checklist import PlatformChecklistFrame
from romm_steam_sync.ui.components.steam_guard_modal import (
    SteamGuardModal,
    run_with_steam_guard,
    show_sync_complete_modal,
)
from romm_steam_sync.ui.components.timeout_modal import RomMTimeoutModal
from romm_steam_sync.ui.helpers import (
    browse_retroarch_executable,
    prompt_timeout_dialog,
    reset_progress_bar,
    test_and_save_romm_credentials,
    update_sync_progress_ui,
    verify_steamgriddb_key,
)

logger = logging.getLogger(__name__)


class OnboardingView(ctk.CTkFrame):
    """Multi-step onboarding wizard for first-time application setup."""

    TOTAL_STEPS = 7

    def __init__(
        self,
        parent,
        settings: AppSettings,
        on_complete: Callable[[], None],
    ):
        super().__init__(parent, fg_color="transparent")
        self.settings = settings
        self.on_complete = on_complete
        self.current_step = 1
        self._cancellation_requested: Optional[str] = None

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header Title & Step Progress
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(15, 4), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header_frame,
            text="Welcome to RomM Steam Sync",
            font=ctk.CTkFont(size=26, weight="bold"),
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.step_indicator_label = ctk.CTkLabel(
            self.header_frame,
            text="Step 1 of 7",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#3498db",
        )
        self.step_indicator_label.grid(row=0, column=1, sticky="e")

        # Step Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self, height=8)
        self.progress_bar.grid(row=1, column=0, padx=20, pady=(3, 8), sticky="ew")
        self.progress_bar.set(1 / self.TOTAL_STEPS)

        # Main Card Content Container
        self.content_card = ctk.CTkFrame(self, corner_radius=12)
        self.content_card.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="nsew")
        self.content_card.grid_columnconfigure(0, weight=1)
        self.content_card.grid_rowconfigure(0, weight=1)

        # Step Sub-Frames
        self.step_frames: List[ctk.CTkFrame] = []
        self._init_step_1_welcome()
        self._init_step_2_romm_server()
        self._init_step_3_retroarch()
        self._init_step_4_steamgriddb()
        self._init_step_5_platforms()
        self._init_step_6_sync()
        self._init_step_7_completion()

        # Display Step 1
        self._show_step(1)

    def _show_step(self, step_num: int):
        """Navigate to a specific step number (1..7)."""
        logger.info("Navigating to onboarding wizard step %d of %d", step_num, self.TOTAL_STEPS)
        self.current_step = step_num
        self.progress_bar.set(step_num / self.TOTAL_STEPS)
        self.step_indicator_label.configure(text=f"Step {step_num} of {self.TOTAL_STEPS}")

        for idx, frame in enumerate(self.step_frames, start=1):
            if idx == step_num:
                pady_val = (10, 10) if step_num in (6, 7) else 20
                frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=pady_val)
            else:
                frame.grid_forget()

        # Step-specific entry actions
        if step_num == 3:
            self._check_retroarch_detection()
        elif step_num == 5:
            self._load_platforms_for_step5()
        elif step_num == 7:
            logger.info("Step 7 reached: marking onboarding_complete = True.")
            self.settings.onboarding_complete = True
            self.settings.save()

    # =========================================================================
    # STEP 1: Welcome Screen
    # =========================================================================
    def _init_step_1_welcome(self):
        frame = ctk.CTkFrame(self.content_card, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        banner = ctk.CTkLabel(
            frame,
            text="RomM Steam Sync",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color="#3498db",
        )
        banner.pack(pady=(20, 10))

        subtitle = ctk.CTkLabel(
            frame,
            text="Bridge your self-hosted RomM game library with Steam seamlessly.",
            font=ctk.CTkFont(size=16),
            text_color="gray",
        )
        subtitle.pack(pady=(0, 20))

        # Features List Card
        features_card = ctk.CTkFrame(frame, corner_radius=8)
        features_card.pack(fill="both", expand=True, padx=20, pady=10)

        features = [
            ("RomM Library Sync", "Export games from your RomM server directly into Steam as Non-Steam game shortcuts."),
            ("Custom Grid Artwork", "Automatically download high-resolution covers, banners, and logos via SteamGridDB."),
            ("Seamless RetroArch Integration", "Launch games instantly from Steam using auto-configured libretro cores."),
            ("Cloud Save Sync", "Sync game saves and play time bidirectionally between your local device and RomM."),
        ]

        for title, desc in features:
            f_box = ctk.CTkFrame(features_card, fg_color="transparent")
            f_box.pack(fill="x", padx=15, pady=10, anchor="w")

            t_lbl = ctk.CTkLabel(f_box, text=title, font=ctk.CTkFont(size=16, weight="bold"))
            t_lbl.pack(anchor="w")

            d_lbl = ctk.CTkLabel(f_box, text=desc, font=ctk.CTkFont(size=14), text_color="gray", justify="left")
            d_lbl.pack(anchor="w", pady=(2, 0))

        # Navigation Bar
        nav_bar = ctk.CTkFrame(frame, fg_color="transparent")
        nav_bar.pack(fill="x", pady=(15, 10))

        next_btn = ctk.CTkButton(
            nav_bar,
            text="Get Started",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=40,
            command=lambda: self._show_step(2),
        )
        next_btn.pack(side="right")

        self.step_frames.append(frame)

    # =========================================================================
    # STEP 2: RomM Server Configuration
    # =========================================================================
    def _init_step_2_romm_server(self):
        frame = ctk.CTkFrame(self.content_card, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="Step 2: RomM Server Configuration",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.pack(anchor="w", pady=(0, 5))

        sub = ctk.CTkLabel(
            frame,
            text="Enter the URL and API key for your RomM server instance.",
            font=ctk.CTkFont(size=15),
            text_color="gray",
        )
        sub.pack(anchor="w", pady=(0, 15))

        # Form Fields Card
        form_card = ctk.CTkFrame(frame, corner_radius=8)
        form_card.pack(fill="x", pady=10)
        form_card.grid_columnconfigure(1, weight=1)

        # Server URL
        ctk.CTkLabel(form_card, text="RomM Server URL:", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=15, pady=12, sticky="w"
        )
        self.step2_url_entry = ctk.CTkEntry(
            form_card, placeholder_text="http://localhost:8080 or https://romm.example.com", font=ctk.CTkFont(size=14)
        )
        self.step2_url_entry.grid(row=0, column=1, padx=15, pady=12, sticky="ew")
        self.step2_url_entry.insert(0, self.settings.romm_url)

        # API Key
        ctk.CTkLabel(form_card, text="API Key:", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=1, column=0, padx=15, pady=12, sticky="w"
        )
        self.step2_key_entry = ctk.CTkEntry(
            form_card, show="*", placeholder_text="RomM API key / bearer token", font=ctk.CTkFont(size=14)
        )
        self.step2_key_entry.grid(row=1, column=1, padx=15, pady=12, sticky="ew")
        self.step2_key_entry.insert(0, self.settings.api_key)

        # Status Label
        self.step2_status_lbl = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=14))
        self.step2_status_lbl.pack(pady=10)

        # Navigation Bar
        nav_bar = ctk.CTkFrame(frame, fg_color="transparent")
        nav_bar.pack(fill="x", side="bottom", pady=10)

        back_btn = ctk.CTkButton(
            nav_bar, text="Back", font=ctk.CTkFont(size=15), fg_color="#34495e", command=lambda: self._show_step(1)
        )
        back_btn.pack(side="left")

        test_next_btn = ctk.CTkButton(
            nav_bar,
            text="Test Connection & Continue",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=40,
            command=self._test_and_save_step2,
        )
        test_next_btn.pack(side="right")

        self.step_frames.append(frame)

    def _test_and_save_step2(self):
        url = self.step2_url_entry.get().strip()
        api_key = self.step2_key_entry.get().strip()

        if not url:
            self.step2_status_lbl.configure(text="RomM Server URL is required.", text_color="#e74c3c")
            return

        self.step2_status_lbl.configure(text="Testing connection to RomM server...", text_color="#3498db")
        self.update_idletasks()

        ok, msg = test_and_save_romm_credentials(
            settings=self.settings,
            url=url,
            api_key=api_key,
            client_cls=RomMApiClient,
            install_launcher=False,
        )
        if ok:
            logger.info("Step 2 RomM server connection test passed!")
            self._show_step(3)
        else:
            logger.warning("Step 2 RomM server test failed: %s", msg)
            self.step2_status_lbl.configure(text=f"Connection failed: {msg}", text_color="#e74c3c")

    # =========================================================================
    # STEP 3: RetroArch Detection & Configuration
    # =========================================================================
    def _init_step_3_retroarch(self):
        frame = ctk.CTkFrame(self.content_card, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="Step 3: RetroArch Detection & Path",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.pack(anchor="w", pady=(0, 5))

        sub = ctk.CTkLabel(
            frame,
            text="RetroArch is used to execute retro ROMs with libretro emulation cores.",
            font=ctk.CTkFont(size=15),
            text_color="gray",
        )
        sub.pack(anchor="w", pady=(0, 15))

        # Status Banner Box
        self.step3_banner = ctk.CTkFrame(frame, corner_radius=8)
        self.step3_banner.pack(fill="x", pady=10)
        self.step3_banner.grid_columnconfigure(0, weight=1)

        self.step3_status_lbl = ctk.CTkLabel(
            self.step3_banner, text="Detecting RetroArch...", font=ctk.CTkFont(size=16, weight="bold")
        )
        self.step3_status_lbl.grid(row=0, column=0, padx=15, pady=12, sticky="w")

        self.step3_path_lbl = ctk.CTkLabel(self.step3_banner, text="", font=ctk.CTkFont(size=14), text_color="gray")
        self.step3_path_lbl.grid(row=1, column=0, padx=15, pady=(0, 12), sticky="w")

        # Action Buttons Container (Steam Store install & Browse manual path)
        self.step3_action_box = ctk.CTkFrame(frame, corner_radius=8)
        self.step3_action_box.pack(fill="x", pady=10)

        steam_btn = ctk.CTkButton(
            self.step3_action_box,
            text="Install RetroArch via Steam Store",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#27ae60",
            hover_color="#2ecc71",
            command=self._open_steam_retroarch_store,
        )
        steam_btn.pack(side="left", padx=15, pady=12)

        browse_btn = ctk.CTkButton(
            self.step3_action_box,
            text="Browse Executable...",
            font=ctk.CTkFont(size=14),
            fg_color="#34495e",
            command=self._browse_retroarch_path,
        )
        browse_btn.pack(side="left", padx=5, pady=12)

        recheck_btn = ctk.CTkButton(
            self.step3_action_box,
            text="Re-detect",
            font=ctk.CTkFont(size=14),
            fg_color="#2980b9",
            command=self._check_retroarch_detection,
        )
        recheck_btn.pack(side="right", padx=15, pady=12)

        # Configuration Card (Flavor + Path)
        path_card = ctk.CTkFrame(frame, corner_radius=8)
        path_card.pack(fill="x", pady=10)
        path_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(path_card, text="Emulator Flavor:", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=15, pady=(12, 6), sticky="w"
        )
        flavor_options = ["Auto-Detect", "Steam RetroArch", "Standalone RetroArch", "RetroDECK"]
        self.step3_flavor_dropdown = ctk.CTkOptionMenu(
            path_card,
            values=flavor_options,
            font=ctk.CTkFont(size=14),
            dropdown_font=ctk.CTkFont(size=14),
            command=self._on_step3_flavor_changed,
        )
        self.step3_flavor_dropdown.grid(row=0, column=1, padx=15, pady=(12, 6), sticky="w")
        current_flavor = getattr(self.settings, "emulator_flavor", "auto").lower()
        flavor_map = {
            "auto": "Auto-Detect",
            "steam": "Steam RetroArch",
            "standalone": "Standalone RetroArch",
            "retrodeck": "RetroDECK",
        }
        self.step3_flavor_dropdown.set(flavor_map.get(current_flavor, "Auto-Detect"))

        ctk.CTkLabel(path_card, text="RetroArch Path:", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=1, column=0, padx=15, pady=(6, 12), sticky="w"
        )
        self.step3_path_entry = ctk.CTkEntry(path_card, font=ctk.CTkFont(size=14), placeholder_text="Path to retroarch.exe or directory")
        self.step3_path_entry.grid(row=1, column=1, padx=15, pady=(6, 12), sticky="ew")
        self.step3_path_entry.insert(0, self.settings.retroarch_path)

        # Navigation Bar
        nav_bar = ctk.CTkFrame(frame, fg_color="transparent")
        nav_bar.pack(fill="x", side="bottom", pady=10)

        back_btn = ctk.CTkButton(
            nav_bar, text="Back", font=ctk.CTkFont(size=15), fg_color="#34495e", command=lambda: self._show_step(2)
        )
        back_btn.pack(side="left")

        next_btn = ctk.CTkButton(
            nav_bar,
            text="Continue",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=40,
            command=self._save_step3_and_next,
        )
        next_btn.pack(side="right")

        self.step_frames.append(frame)

    def _on_step3_flavor_changed(self, choice: str) -> None:
        """Handle emulator flavor dropdown change in onboarding."""
        val_map = {
            "Auto-Detect": "auto",
            "Steam RetroArch": "steam",
            "Standalone RetroArch": "standalone",
            "RetroDECK": "retrodeck",
        }
        self.settings.emulator_flavor = val_map.get(choice, "auto")
        self._check_retroarch_detection()

    def _check_retroarch_detection(self):
        logger.info("Running RetroArch auto-detection...")
        configured = self.step3_path_entry.get().strip() or self.settings.retroarch_path
        flavor = getattr(self.settings, "emulator_flavor", "auto")
        adapter = get_retroarch_adapter(configured, flavor=flavor)
        detected = adapter.resolve_binary()

        if detected:
            logger.info("RetroArch detected at: %s", detected)
            flavor_name = adapter.flavor.name.title()
            if adapter.flavor.name == "STEAM":
                flavor_name = "Steam RetroArch"
            elif adapter.flavor.name == "STANDALONE":
                flavor_name = "Standalone RetroArch"
            elif adapter.flavor.name == "RETRODECK":
                flavor_name = "RetroDECK"

            self.step3_status_lbl.configure(
                text=f"{flavor_name} Detected Successfully!",
                text_color="#2ecc71",
            )
            self.step3_path_lbl.configure(text=f"Location: {detected}")
            if not self.step3_path_entry.get().strip():
                self.step3_path_entry.delete(0, "end")
                self.step3_path_entry.insert(0, detected)
        else:
            logger.warning("RetroArch binary not detected on system.")
            self.step3_status_lbl.configure(
                text="RetroArch Not Detected Automatically", text_color="#e67e22"
            )
            self.step3_path_lbl.configure(
                text="Please install RetroArch via Steam or specify the RetroArch installation directory below."
            )

    def _open_steam_retroarch_store(self):
        url = "steam://store/1118310"
        logger.info("Opening Steam Store page for RetroArch: %s", url)
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.error("Failed to open Steam store link: %s", e)
            webbrowser.open("https://store.steampowered.com/app/1118310/RetroArch/")

    def _browse_retroarch_path(self):
        chosen = browse_retroarch_executable(parent=self)
        if chosen:
            self.step3_path_entry.delete(0, "end")
            self.step3_path_entry.insert(0, chosen)
            self._check_retroarch_detection()

    def _save_step3_and_next(self):
        path = self.step3_path_entry.get().strip()
        self.settings.retroarch_path = path
        if hasattr(self, "step3_flavor_dropdown"):
            choice = self.step3_flavor_dropdown.get()
            val_map = {
                "Auto-Detect": "auto",
                "Steam RetroArch": "steam",
                "Standalone RetroArch": "standalone",
                "RetroDECK": "retrodeck",
            }
            self.settings.emulator_flavor = val_map.get(choice, "auto")
        self.settings.save()
        self._show_step(4)

    # =========================================================================
    # STEP 4: SteamGridDB API Key (Optional)
    # =========================================================================
    def _init_step_4_steamgriddb(self):
        frame = ctk.CTkFrame(self.content_card, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="Step 4: SteamGridDB API Key (Optional)",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.pack(anchor="w", pady=(0, 5))

        sub = ctk.CTkLabel(
            frame,
            text="SteamGridDB provides custom game covers, vertical grids, hero banners, and logos for Steam.",
            font=ctk.CTkFont(size=15),
            text_color="gray",
        )
        sub.pack(anchor="w", pady=(0, 15))

        # Instructions Card
        instr_card = ctk.CTkFrame(frame, corner_radius=8)
        instr_card.pack(fill="x", pady=10)

        instructions = (
            "How to get a SteamGridDB API Key:\n"
            "1. Visit www.steamgriddb.com and log in with your Steam account.\n"
            "2. Open your Profile Settings -> API section.\n"
            "3. Click 'Generate API Key', copy it, and paste it into the field below."
        )
        ins_lbl = ctk.CTkLabel(
            instr_card, text=instructions, font=ctk.CTkFont(size=14), justify="left", text_color="#ecf0f1"
        )
        ins_lbl.pack(anchor="w", padx=15, pady=12)

        link_btn = ctk.CTkButton(
            instr_card,
            text="Open SteamGridDB API Settings Page",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#34495e",
            command=lambda: webbrowser.open("https://www.steamgriddb.com/profile/api"),
        )
        link_btn.pack(anchor="w", padx=15, pady=(0, 12))

        # Key Input Card
        key_card = ctk.CTkFrame(frame, corner_radius=8)
        key_card.pack(fill="x", pady=10)
        key_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(key_card, text="SteamGridDB API Key:", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, padx=15, pady=12, sticky="w"
        )
        self.step4_key_entry = ctk.CTkEntry(
            key_card, placeholder_text="Optional API Key string...", font=ctk.CTkFont(size=14)
        )
        self.step4_key_entry.grid(row=0, column=1, padx=15, pady=12, sticky="ew")
        self.step4_key_entry.insert(0, self.settings.steamgriddb_api_key)

        test_key_btn = ctk.CTkButton(
            key_card, text="Test Key", font=ctk.CTkFont(size=14), command=self._test_sgdb_key
        )
        test_key_btn.grid(row=0, column=2, padx=15, pady=12)

        self.step4_status_lbl = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=14))
        self.step4_status_lbl.pack(pady=5)

        # Navigation Bar
        nav_bar = ctk.CTkFrame(frame, fg_color="transparent")
        nav_bar.pack(fill="x", side="bottom", pady=10)

        back_btn = ctk.CTkButton(
            nav_bar, text="Back", font=ctk.CTkFont(size=15), fg_color="#34495e", command=lambda: self._show_step(3)
        )
        back_btn.pack(side="left")

        skip_btn = ctk.CTkButton(
            nav_bar,
            text="Skip for Now",
            font=ctk.CTkFont(size=15),
            fg_color="#7f8c8d",
            hover_color="#95a5a6",
            command=lambda: self._show_step(5),
        )
        skip_btn.pack(side="right", padx=(10, 0))

        next_btn = ctk.CTkButton(
            nav_bar,
            text="Save & Continue",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=40,
            command=self._save_step4_and_next,
        )
        next_btn.pack(side="right")

        self.step_frames.append(frame)

    def _test_sgdb_key(self) -> None:
        """Test user entered SteamGridDB API key against SGDB API."""
        key = self.step4_key_entry.get().strip()
        if not key:
            self.step4_status_lbl.configure(
                text="Please enter an API Key to test.", text_color="#e67e22"
            )
            return

        self.step4_status_lbl.configure(
            text="Testing SteamGridDB API key...", text_color="#3498db"
        )
        self.update_idletasks()

        ok, msg = verify_steamgriddb_key(key, client_cls=SteamGridDbClient)
        if ok:
            self.step4_status_lbl.configure(text=msg, text_color="#2ecc71")
        else:
            self.step4_status_lbl.configure(text=msg, text_color="#e74c3c")

    def _save_step4_and_next(self):
        key = self.step4_key_entry.get().strip()
        self.settings.steamgriddb_api_key = key
        self.settings.save()
        self._show_step(5)

    # =========================================================================
    # STEP 5: Platform Selection
    # =========================================================================
    def _init_step_5_platforms(self):
        frame = ctk.CTkFrame(self.content_card, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="Step 5: Platform Selection",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 5))

        sub = ctk.CTkLabel(
            frame,
            text="Select which gaming platforms from your RomM library to export into Steam.",
            font=ctk.CTkFont(size=15),
            text_color="gray",
        )
        sub.grid(row=1, column=0, sticky="w", pady=(0, 10))

        # Platform Selection Control Bar (Select All & Deselect All)
        ctrl_bar = ctk.CTkFrame(frame, fg_color="transparent")
        ctrl_bar.grid(row=2, column=0, sticky="w", pady=(0, 5))

        self.step5_select_all_btn = ctk.CTkButton(
            ctrl_bar,
            text="Select All",
            command=self._step5_select_all,
            font=ctk.CTkFont(size=14),
            width=110,
            fg_color="#34495e",
        )
        self.step5_select_all_btn.pack(side="left", padx=(0, 10))

        self.step5_deselect_all_btn = ctk.CTkButton(
            ctrl_bar,
            text="Deselect All",
            command=self._step5_deselect_all,
            font=ctk.CTkFont(size=14),
            width=110,
            fg_color="#34495e",
        )
        self.step5_deselect_all_btn.pack(side="left")

        # Scrollable Platforms Checklist
        self.step5_checklist = PlatformChecklistFrame(
            frame, label_text="Available RomM Platforms", height=320
        )
        self.step5_checklist.grid(row=3, column=0, sticky="nsew", pady=10)
        self.step5_vars = self.step5_checklist.checkbox_vars

        # Status Label
        self.step5_status_lbl = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=14))
        self.step5_status_lbl.grid(row=4, column=0, pady=5)

        # Navigation Bar
        nav_bar = ctk.CTkFrame(frame, fg_color="transparent")
        nav_bar.grid(row=5, column=0, sticky="ew", pady=10)

        back_btn = ctk.CTkButton(
            nav_bar, text="Back", font=ctk.CTkFont(size=15), fg_color="#34495e", command=lambda: self._show_step(4)
        )
        back_btn.pack(side="left")

        next_btn = ctk.CTkButton(
            nav_bar,
            text="Save & Continue to Sync",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=40,
            command=self._save_step5_and_next,
        )
        next_btn.pack(side="right")

        self.step_frames.append(frame)

    def _step5_select_all(self) -> None:
        """Select all platform checkboxes in Step 5."""
        logger.info("Step 5: Selecting all platforms.")
        for var in self.step5_vars.values():
            var.set(True)

    def _step5_deselect_all(self) -> None:
        """Deselect all platform checkboxes in Step 5."""
        logger.info("Step 5: Deselecting all platforms.")
        for var in self.step5_vars.values():
            var.set(False)

    def _load_platforms_for_step5(self):
        logger.info("Step 5 loading platforms from RomM server...")
        client = RomMApiClient(
            base_url=self.settings.romm_url,
            api_key=self.settings.api_key,
        )
        self.step5_checklist.load_platforms(
            settings=self.settings,
            client=client,
            on_status=lambda msg, color: self.step5_status_lbl.configure(text=msg, text_color=color),
        )

    def _save_step5_and_next(self):
        selected = self.step5_checklist.save_selections(self.settings)
        self._show_step(6)

    # =========================================================================
    # STEP 6: Library Sync
    # =========================================================================
    def _init_step_6_sync(self):
        frame = ctk.CTkFrame(self.content_card, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="Step 6: Initial Library Synchronization",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 2))

        sub = ctk.CTkLabel(
            frame,
            text="Initial library sync from RomM to Steam. Steam must be closed and remain closed while this is running.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        )
        sub.grid(row=1, column=0, sticky="w", pady=(0, 6))

        # Sync Action Card
        sync_card = ctk.CTkFrame(frame, corner_radius=8)
        sync_card.grid(row=2, column=0, sticky="ew", pady=(3, 6))
        sync_card.grid_columnconfigure(0, weight=1)

        # Action Buttons Layout (Start Sync & Cancel Sync)
        btn_bar = ctk.CTkFrame(sync_card, fg_color="transparent")
        btn_bar.pack(fill="x", padx=15, pady=(8, 4))
        btn_bar.grid_columnconfigure(0, weight=3)
        btn_bar.grid_columnconfigure(1, weight=1)

        self.step6_start_btn = ctk.CTkButton(
            btn_bar,
            text="Start Initial Sync",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=36,
            fg_color="#2980b9",
            hover_color="#3498db",
            command=self._start_initial_sync,
        )
        self.step6_start_btn.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.step6_cancel_btn = ctk.CTkButton(
            btn_bar,
            text="Cancel Sync",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=36,
            fg_color="#e74c3c",
            hover_color="#c0392b",
            state="disabled",
            command=self._on_step6_cancel_clicked,
        )
        self.step6_cancel_btn.grid(row=0, column=1, sticky="ew")

        self.step6_progress_bar = ctk.CTkProgressBar(sync_card)
        self.step6_progress_bar.pack(fill="x", padx=15, pady=(0, 4))
        self.step6_progress_bar.set(0.0)

        self.step6_status_lbl = ctk.CTkLabel(
            sync_card, text="Ready to start sync.", font=ctk.CTkFont(size=14)
        )
        self.step6_status_lbl.pack(pady=(0, 6))

        # Rom Cover Conveyor Component
        self.step6_conveyor = RomCoverConveyor(frame)
        self.step6_conveyor.grid(row=3, column=0, sticky="nsew", pady=(4, 6))

        # Navigation Bar
        nav_bar = ctk.CTkFrame(frame, fg_color="transparent")
        nav_bar.grid(row=4, column=0, sticky="ew", pady=(4, 6))

        self.step6_back_btn = ctk.CTkButton(
            nav_bar, text="Back", font=ctk.CTkFont(size=15), fg_color="#34495e", height=36, command=lambda: self._show_step(5)
        )
        self.step6_back_btn.pack(side="left")

        self.step6_finish_btn = ctk.CTkButton(
            nav_bar,
            text="Continue",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=36,
            fg_color="#27ae60",
            hover_color="#2ecc71",
            state="disabled",
            command=lambda: self._show_step(7),
        )
        self.step6_finish_btn.pack(side="right")

        self.step_frames.append(frame)

    def _start_initial_sync(self):
        logger.info("User started initial sync in onboarding wizard...")
        top = self.winfo_toplevel() if hasattr(self, "winfo_toplevel") else self
        run_with_steam_guard(top, on_proceed=self._run_wizard_sync_thread)

    def _on_step6_cancel_clicked(self):
        """Open cancel modal dialog to prompt user for Cancel or Rollback choice."""
        logger.info("User clicked Cancel Sync button in onboarding step 6.")
        top = self.winfo_toplevel() if hasattr(self, "winfo_toplevel") else self
        SyncCancelModal(top, on_choice=self._handle_step6_cancel_choice)

    def _handle_step6_cancel_choice(self, choice: str):
        """Handle user choice from SyncCancelModal in onboarding step 6."""
        logger.info("User selected step 6 cancel choice: %s", choice)
        if choice in ("cancel", "rollback"):
            self._cancellation_requested = choice
            self.step6_status_lbl.configure(text=f"Cancelling sync pass ({choice})...")

    def _run_wizard_sync_thread(self):
        self.step6_start_btn.configure(state="disabled")
        self.step6_cancel_btn.configure(state="normal")
        self.step6_finish_btn.configure(state="disabled")
        self.step6_back_btn.configure(state="disabled")
        reset_progress_bar(self.step6_progress_bar, mode="determinate", value=0.0)
        self.step6_status_lbl.configure(
            text="Starting library synchronization pass...", text_color="#ecf0f1"
        )
        self._cancellation_requested = None
        self.step6_conveyor.clear()
        self.step6_conveyor.append_log("Starting initial library sync pass...")

        thread = threading.Thread(target=self._wizard_sync_worker, daemon=True)
        thread.start()

    def _prompt_step6_on_timeout(self, platform_name: str, backup_id: Optional[str]) -> str:
        """Thread-safe invocation of RomMTimeoutModal on GUI thread in wizard step 6."""
        return prompt_timeout_dialog(
            self,
            self.step6_progress_bar,
            platform_name,
            backup_id,
            modal_cls=RomMTimeoutModal,
        )

    def _wizard_sync_worker(self) -> None:
        sync_service = SyncService(settings=self.settings)

        def progress_cb(
            pct: float,
            msg: str,
            cover_path: Optional[str] = None,
            rom_name: Optional[str] = None,
        ) -> None:
            """Emit wizard synchronization progress to UI.

            Args:
                pct: Progress fraction from 0.0 to 1.0 (or negative for indeterminate).
                msg: Status message.
                cover_path: Optional path to game artwork image.
                rom_name: Optional title of game.
            """
            self.after(
                0, lambda: self._update_step6_ui(pct, msg, cover_path, rom_name)
            )

        try:
            success, message, count = sync_service.sync_library(
                progress_callback=progress_cb,
                skip_steam_guard=True,
                on_timeout_callback=self._prompt_step6_on_timeout,
                is_cancelled_callback=lambda: self._cancellation_requested,
            )
            self.after(0, lambda: self._on_step6_finished(success, message, count))
        except SteamRunningException as e:
            logger.error("Step 6 sync worker blocked by running Steam: %s", e)
            self.after(0, lambda: self._on_step6_finished(False, str(e), 0))
        except Exception as e:
            logger.error("Step 6 sync worker exception: %s", e, exc_info=True)
            self.after(0, lambda: self._on_step6_finished(False, f"Error: {e}", 0))

    def _update_step6_ui(
        self,
        pct: float,
        msg: str,
        cover_path: Optional[str] = None,
        rom_name: Optional[str] = None,
    ) -> None:
        """Update progress bar, status label, and animated conveyor on the onboarding UI.

        Args:
            pct: Progress fraction from 0.0 to 1.0 (or negative for indeterminate).
            msg: Status message to display.
            cover_path: Optional artwork path.
            rom_name: Optional ROM title.
        """
        update_sync_progress_ui(
            progress_bar=self.step6_progress_bar,
            status_lbl=self.step6_status_lbl,
            conveyor=self.step6_conveyor,
            pct=pct,
            msg=msg,
            cover_path=cover_path,
            rom_name=rom_name,
        )

    def _on_step6_finished(self, success: bool, message: str, count: int) -> None:
        """Handle completion or failure of the onboarding sync worker thread.

        Args:
            success: True if sync finished successfully.
            message: Result or error message string.
            count: Number of synced games.
        """
        self.step6_start_btn.configure(state="normal")
        self.step6_cancel_btn.configure(state="disabled")
        self.step6_finish_btn.configure(state="normal")
        self.step6_back_btn.configure(state="normal")
        reset_progress_bar(self.step6_progress_bar, mode="determinate")

        if success:
            logger.info("Onboarding initial sync completed: %s (%d items)", message, count)
            self.step6_progress_bar.set(1.0)
            self.step6_status_lbl.configure(text=message, text_color="#2ecc71")
            self.step6_conveyor.append_log(f"SUCCESS: {message}")
            top = self.winfo_toplevel() if hasattr(self, "winfo_toplevel") else self
            show_sync_complete_modal(top)
        else:
            logger.warning("Onboarding initial sync ended with warning/error: %s", message)
            self.step6_status_lbl.configure(
                text=message,
                text_color="#e67e22" if "cancelled" in message.lower() else "#e74c3c",
            )
            self.step6_conveyor.append_log(f"STATUS: {message}")

    def _complete_onboarding(self):
        logger.info("User clicked Finish Onboarding. Marking onboarding_complete = True.")
        self.settings.onboarding_complete = True
        self.settings.save()
        self.on_complete()

    # =========================================================================
    # STEP 7: Onboarding Completion
    # =========================================================================
    def _init_step_7_completion(self) -> None:
        """Initialize the final step 7 completion card."""
        frame = ctk.CTkFrame(self.content_card, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="Step 7: Setup Complete",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        title.pack(anchor="w", pady=(0, 5))

        sub = ctk.CTkLabel(
            frame,
            text="Your initial configuration and library synchronization are complete.",
            font=ctk.CTkFont(size=15),
            text_color="gray",
        )
        sub.pack(anchor="w", pady=(0, 15))

        # Completion Message Card
        msg_card = ctk.CTkFrame(frame, corner_radius=8)
        msg_card.pack(fill="both", expand=True, padx=10, pady=15)
        msg_card.grid_columnconfigure(0, weight=1)

        heading = ctk.CTkLabel(
            msg_card,
            text="Ready to Play!",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#2ecc71",
        )
        heading.pack(pady=(35, 15))

        message_text = (
            "Library sync is complete, you can re-open Steam and your games "
            "should appear in Library > Collections. If you want to uninstall "
            "or manage games come back to this app. Press \"Finish\" to finalize "
            "onboarding."
        )

        self.step7_msg_label = ctk.CTkLabel(
            msg_card,
            text=message_text,
            font=ctk.CTkFont(size=16),
            justify="center",
            wraplength=650,
        )
        self.step7_msg_label.pack(padx=30, pady=(0, 35))

        # Navigation Bar
        nav_bar = ctk.CTkFrame(frame, fg_color="transparent")
        nav_bar.pack(fill="x", side="bottom", pady=10)

        back_btn = ctk.CTkButton(
            nav_bar,
            text="Back",
            font=ctk.CTkFont(size=15),
            fg_color="#34495e",
            command=lambda: self._show_step(6),
        )
        back_btn.pack(side="left")

        self.step7_finish_btn = ctk.CTkButton(
            nav_bar,
            text="Finish",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=40,
            fg_color="#27ae60",
            hover_color="#2ecc71",
            command=self._complete_onboarding,
        )
        self.step7_finish_btn.pack(side="right")

        self.step_frames.append(frame)

