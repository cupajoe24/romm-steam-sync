"""CustomTkinter GUI Window for On-Demand ROM Download and Execution with Save Sync."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from romm_steam_sync.adapters.retroarch_launcher import (
    DEFAULT_CORE_MAPPINGS,
    RetroArchLauncher,
)
from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.config import AppSettings
from romm_steam_sync.launcher.formatters import format_size, format_version_display
from romm_steam_sync.launcher.services.download_service import RomDownloadService
from romm_steam_sync.launcher.services.file_resolver import LocalRomResolver
from romm_steam_sync.launcher.services.process_supervisor import GameProcessSupervisor
from romm_steam_sync.launcher.services.save_coordinator import SaveCoordinator
from romm_steam_sync.launcher.views.error_view import ErrorDisplayManager
from romm_steam_sync.launcher.views.status_card import StatusCardView
from romm_steam_sync.launcher.views.version_select_view import VersionSelectView
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.service_layer.save_sync import find_local_save_file
from romm_steam_sync.ui.theme import (
    COLOR_INFO,
    COLOR_INFO_HOVER,
    COLOR_NEUTRAL,
    COLOR_PURPLE,
    COLOR_PURPLE_HOVER,
    COLOR_SUCCESS,
    COLOR_SUCCESS_HOVER,
    COLOR_TEXT,
    COLOR_WARNING,
)
from romm_steam_sync.version import __version__

logger = logging.getLogger(__name__)


class LauncherWindow(ctk.CTk):
    """Modern dark-themed GUI popup window for Steam game execution & on-demand download."""

    def __init__(self, rom_id: int, platform_slug: str = ""):
        """Initialize LauncherWindow.

        Args:
            rom_id: Unique RomM ROM identifier.
            platform_slug: Target platform identifier.
        """
        super().__init__()
        self.rom_id = rom_id
        self.platform_slug = platform_slug.lower()
        self.settings = AppSettings.load()
        self.db_session = DatabaseSession()

        # Instantiate Services
        self.file_resolver = LocalRomResolver(db_session=self.db_session)
        self.download_service = RomDownloadService(db_session=self.db_session)
        self.process_supervisor = GameProcessSupervisor()
        self.save_coordinator = SaveCoordinator(settings=self.settings)

        self.title("RomM Steam Sync Launcher")
        self.geometry("620x420")
        self.minsize(580, 380)
        self.resizable(True, True)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # State tracking
        self.rom_data: Dict[str, Any] = {}
        self.rom_name: str = f"ROM #{rom_id}"
        self.file_name: str = ""
        self.file_size: int = 0
        self.local_file_path: Optional[str] = None
        self.is_downloading: bool = False
        self.is_game_running: bool = False
        self.auto_launch_timer: Optional[threading.Timer] = None
        self.all_versions: List[Dict[str, Any]] = []
        self.sibling_group_key: Optional[str] = None
        self.session_start_time: Optional[datetime] = None
        self.session_start_mono: Optional[float] = None

        self.protocol("WM_DELETE_WINDOW", self._on_window_close)
        self._build_ui()

        # Bring window to foreground when launcher opens
        try:
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self._safe_after(300, self._clear_topmost)
        except Exception as e:
            logger.debug("Failed setting initial topmost window attribute: %s", e)

        # Start initial inspection in background thread
        threading.Thread(target=self._inspect_rom_state, daemon=True).start()

    def _clear_topmost(self) -> None:
        """Release topmost attribute after window is focused."""
        try:
            self.attributes("-topmost", False)
        except Exception as e:
            logger.debug("Failed clearing topmost attribute: %s", e)

    def _safe_after(self, ms: int, func: Any, *args: Any) -> None:
        """Schedule a callback on the GUI thread safely."""
        try:
            self.after(ms, func, *args)
        except Exception as e:
            logger.debug("Failed scheduling callback via self.after: %s", e)

    def _on_window_close(self) -> None:
        """Handle window close attempt safely during game execution."""
        if self.is_game_running:
            logger.warning("Window close attempt prevented while game '%s' is actively running.", self.rom_name)
            return
        self.destroy()

    def _build_ui(self) -> None:
        """Construct launcher window widgets and sub-views."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header Frame
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            header_frame,
            text=f"Loading ROM #{self.rom_id}...",
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.platform_badge = ctk.CTkLabel(
            header_frame,
            text=(self.platform_slug.upper() if self.platform_slug else "ROMM"),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_NEUTRAL,
            text_color=COLOR_TEXT,
            corner_radius=6,
            padx=10,
            pady=4,
        )
        self.platform_badge.grid(row=0, column=1, sticky="e")

        # Status Card View
        self.status_card = StatusCardView(master=self)

        # Re-export widget references for backward compatibility
        self.card_frame = self.status_card.card_frame
        self.status_title_label = self.status_card.status_title_label
        self.detail_label = self.status_card.detail_label
        self.progress_bar = self.status_card.progress_bar
        self.action_frame = self.status_card.action_frame
        self.cancel_btn = self.status_card.cancel_btn
        self.action_btn = self.status_card.action_btn

        self.cancel_btn.configure(command=self.destroy)

        # Error Display Manager
        self.error_manager = ErrorDisplayManager(
            window=self,
            card_frame=self.card_frame,
            detail_label=self.detail_label,
            status_title_label=self.status_title_label,
            action_frame=self.action_frame,
            cancel_btn=self.cancel_btn,
            action_btn=self.action_btn,
            progress_bar=self.progress_bar,
        )
        self.error_textbox = self.error_manager.error_textbox
        self.copy_error_btn = self.error_manager.copy_error_btn

        # Version Select View
        self.version_select_view = VersionSelectView(
            card_frame=self.card_frame,
            db_session=self.db_session,
        )

        # Version Display (Bottom Right)
        self.version_label = ctk.CTkLabel(
            self,
            text=f"v{__version__}",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.version_label.grid(row=3, column=0, padx=20, pady=(0, 8), sticky="se")

    @property
    def _last_error_text(self) -> str:
        return self.error_manager._last_error_text

    @_last_error_text.setter
    def _last_error_text(self, val: str) -> None:
        self.error_manager._last_error_text = val

    def _show_error_state(
        self,
        title: str,
        message: str,
        full_details: Optional[str] = None,
        retry_command: Optional[Callable[[], None]] = None,
        retry_text: str = "Retry",
    ) -> None:
        """Display an error in the launcher with selectable text and copy button."""
        header_info = (
            f"Game: {self.rom_name} "
            f"(ROM ID: {self.rom_id}, Platform: {self.platform_slug.upper() if self.platform_slug else 'ROMM'})"
        )
        self.error_manager.show_error_state(
            title=title,
            message=message,
            header_info=header_info,
            full_details=full_details,
            retry_command=retry_command,
            retry_text=retry_text,
            on_close=self.destroy,
        )

    def _clear_error_state(self) -> None:
        """Reset error display widgets back to normal status presentation."""
        self.error_manager.clear_error_state()

    def _copy_error_to_clipboard(self) -> None:
        """Copy structured error details to system clipboard."""
        self.error_manager.copy_error_to_clipboard()

    def _inspect_rom_state(self) -> None:
        """Inspect ROM state, discover sibling versions, and handle version selection if needed."""
        logger.info("Launcher window initialized for rom_id %s (platform: %s)", self.rom_id, self.platform_slug)
        with self.db_session as db:
            rom_entity = db.roms.get(self.rom_id)
            if rom_entity:
                self.rom_name = rom_entity.name
                self.sibling_group_key = rom_entity.sibling_group_key
                if not self.platform_slug and rom_entity.platform_slug:
                    self.platform_slug = rom_entity.platform_slug.lower()

            siblings = db.roms.get_siblings(self.rom_id) if self.rom_id else []

        client = RomMApiClient(base_url=self.settings.romm_url, api_key=self.settings.api_key)
        rom_detail: Dict[str, Any] = {}
        try:
            rom_detail = client.get_rom_detail(self.rom_id)
        except Exception as e:
            logger.warning("Could not fetch ROM detail from RomM API for rom_id %s: %s", self.rom_id, e)

        version_dict: Dict[int, Dict[str, Any]] = {}
        with self.db_session as db:
            for s in siblings:
                inst = db.installs.get(s.rom_id)
                version_dict[s.rom_id] = {
                    "id": s.rom_id,
                    "name": s.name,
                    "fs_name": s.fs_name,
                    "platform_slug": s.platform_slug,
                    "is_installed": inst is not None and Path(inst.file_path).exists() if inst else False,
                    "file_path": inst.file_path if inst else None,
                }

            if self.rom_id not in version_dict:
                inst = db.installs.get(self.rom_id)
                version_dict[self.rom_id] = {
                    "id": self.rom_id,
                    "name": self.rom_name,
                    "fs_name": self.file_name,
                    "platform_slug": self.platform_slug,
                    "is_installed": inst is not None and Path(inst.file_path).exists() if inst else False,
                    "file_path": inst.file_path if inst else None,
                }

        if rom_detail and self.rom_id in version_dict:
            curr_v = version_dict[self.rom_id]
            curr_v["name"] = rom_detail.get("name") or curr_v["name"]
            curr_v["fs_name"] = rom_detail.get("fs_name") or rom_detail.get("file_name") or curr_v.get("fs_name")
            curr_v["fs_name_no_ext"] = rom_detail.get("fs_name_no_ext")
            curr_v["fs_name_no_tags"] = rom_detail.get("fs_name_no_tags")
            curr_v["file_size"] = rom_detail.get("fs_size_bytes") or self.file_size
            curr_v["revision"] = rom_detail.get("revision")
            curr_v["regions"] = rom_detail.get("regions")
            curr_v["languages"] = rom_detail.get("languages")
            curr_v["tags"] = rom_detail.get("tags")
            curr_v["disc"] = rom_detail.get("disc")

        if rom_detail and isinstance(rom_detail.get("sibling_roms"), list):
            with self.db_session as db:
                for sib in rom_detail["sibling_roms"]:
                    s_id = sib.get("id") or sib.get("rom_id")
                    if not s_id:
                        continue
                    inst = db.installs.get(s_id)
                    is_inst = inst is not None and Path(inst.file_path).exists() if inst else False

                    if s_id not in version_dict:
                        version_dict[s_id] = {
                            "id": s_id,
                            "name": sib.get("name") or f"Version #{s_id}",
                            "platform_slug": self.platform_slug,
                            "is_installed": is_inst,
                            "file_path": inst.file_path if inst else None,
                        }
                    entry = version_dict[s_id]
                    if sib.get("name"):
                        entry["name"] = sib.get("name")
                    if sib.get("fs_name"):
                        entry["fs_name"] = sib.get("fs_name")
                    if sib.get("fs_name_no_ext"):
                        entry["fs_name_no_ext"] = sib.get("fs_name_no_ext")
                    if sib.get("fs_name_no_tags"):
                        entry["fs_name_no_tags"] = sib.get("fs_name_no_tags")
                    if sib.get("revision"):
                        entry["revision"] = sib.get("revision")
                    if sib.get("regions"):
                        entry["regions"] = sib.get("regions")
                    if sib.get("languages"):
                        entry["languages"] = sib.get("languages")
                    if sib.get("tags"):
                        entry["tags"] = sib.get("tags")
                    if sib.get("fs_size_bytes"):
                        entry["file_size"] = sib.get("fs_size_bytes")
                    if sib.get("disc"):
                        entry["disc"] = sib.get("disc")

        if len(version_dict) > 1:
            for s_id, v in version_dict.items():
                if s_id != self.rom_id and not v.get("fs_name_no_ext") and not v.get("fs_name"):
                    try:
                        s_detail = client.get_rom_detail(s_id)
                        if s_detail:
                            v["name"] = s_detail.get("name") or v["name"]
                            v["fs_name"] = s_detail.get("fs_name") or s_detail.get("file_name") or v.get("fs_name")
                            v["fs_name_no_ext"] = s_detail.get("fs_name_no_ext")
                            v["fs_name_no_tags"] = s_detail.get("fs_name_no_tags")
                            v["revision"] = s_detail.get("revision")
                            v["regions"] = s_detail.get("regions")
                            v["languages"] = s_detail.get("languages")
                            v["tags"] = s_detail.get("tags")
                            v["disc"] = s_detail.get("disc")
                            v["file_size"] = s_detail.get("fs_size_bytes") or v.get("file_size")
                    except Exception as e:
                        logger.debug("Could not fetch extra sibling detail for %s: %s", s_id, e)

        self.all_versions = list(version_dict.values())

        if len(self.all_versions) > 1:
            with self.db_session as db:
                saved_pref = None
                if self.sibling_group_key:
                    saved_pref = db.kv_config.get(f"default_version:{self.sibling_group_key}")
                if not saved_pref:
                    saved_pref = db.kv_config.get(f"default_version:{self.rom_id}")

                if saved_pref and saved_pref.value and saved_pref.value.isdigit():
                    pref_id = int(saved_pref.value)
                    if any(v["id"] == pref_id for v in self.all_versions):
                        logger.info("Found saved default version %s for game group %s", pref_id, self.sibling_group_key)
                        self.rom_id = pref_id
                        self._inspect_single_rom_state(rom_detail if (rom_detail.get("id") == pref_id) else None)
                        return

            self._safe_after(0, self._show_version_selection_state)
        else:
            self._inspect_single_rom_state(rom_detail)

    def _show_version_selection_state(self) -> None:
        """Update UI to present interactive version / disc selection screen."""
        self.geometry("640x540")
        self.minsize(600, 480)
        self.title_label.configure(text=self.rom_name)
        self.platform_badge.configure(text=self.platform_slug.upper() if self.platform_slug else "ROMM")

        self.status_card.set_status(
            title="Select Version / Disc",
            detail="This game has multiple versions or discs. Select which version to launch:",
            title_color=COLOR_INFO_HOVER,
            detail_color=COLOR_TEXT,
        )

        self.version_select_view.build_version_list(
            versions=self.all_versions,
            current_rom_id=self.rom_id,
            canonical_name=self.rom_name,
        )

        self.status_card.configure_cancel_button(text="Cancel", command=self.destroy, state="normal")
        self.status_card.configure_action_button(
            text="Launch Version",
            fg_color=COLOR_INFO,
            hover_color=COLOR_INFO_HOVER,
            state="normal",
            command=self._on_version_selected,
        )
        self.status_card.show_action_frame()

    def _on_version_selected(self) -> None:
        """Handle user confirmation of version choice with optional persistence."""
        selected_id = self.version_select_view.get_selected_version(default_id=self.rom_id)
        self.version_select_view.persist_preference_if_checked(
            selected_id=selected_id,
            rom_id=self.rom_id,
            sibling_group_key=self.sibling_group_key,
        )
        self.version_select_view.cleanup()

        self.geometry("620x420")
        self.minsize(580, 380)
        self.rom_id = selected_id

        for v in self.all_versions:
            if v["id"] == selected_id:
                self.rom_name = v["name"]
                break

        self.status_card.set_status(
            title="Loading Selected Version...",
            detail=f"Preparing {self.rom_name}...",
            title_color=COLOR_INFO_HOVER,
        )
        self.status_card.configure_action_button(text="Please Wait...", command=None, state="disabled")

        threading.Thread(target=self._inspect_single_rom_state, daemon=True).start()

    def _inspect_single_rom_state(self, pre_fetched_detail: Optional[Dict[str, Any]] = None) -> None:
        """Fetch ROM metadata and check local file existence for active ROM ID."""
        with self.db_session as db:
            rom_entity = db.roms.get(self.rom_id)
        if rom_entity:
            self.rom_name = rom_entity.name
            if not self.platform_slug and rom_entity.platform_slug:
                self.platform_slug = rom_entity.platform_slug.lower()

        client = RomMApiClient(base_url=self.settings.romm_url, api_key=self.settings.api_key)
        rom_detail: Dict[str, Any] = pre_fetched_detail or {}
        if not rom_detail:
            try:
                rom_detail = client.get_rom_detail(self.rom_id)
            except Exception as e:
                logger.warning("Could not fetch ROM detail from RomM API for rom_id %s: %s", self.rom_id, e)

        if rom_detail:
            self.rom_data = rom_detail
            self.rom_name = rom_detail.get("name") or self.rom_name
            p_slug_raw = rom_detail.get("platform_slug") or (
                rom_detail.get("platform", {}).get("slug") if isinstance(rom_detail.get("platform"), dict) else None
            )
            if p_slug_raw:
                self.platform_slug = str(p_slug_raw).lower()

            self.file_name = (
                rom_detail.get("fs_name")
                or rom_detail.get("file_name")
                or rom_detail.get("filename")
                or rom_detail.get("path")
            )
            if not self.file_name and isinstance(rom_detail.get("files"), list) and rom_detail["files"]:
                first_f = rom_detail["files"][0]
                if isinstance(first_f, dict):
                    self.file_name = first_f.get("file_name") or first_f.get("filename") or first_f.get("name")

            if not self.file_name:
                self.file_name = f"{self.rom_name}.rom"

            size_val = (
                rom_detail.get("fs_size_bytes")
                or rom_detail.get("file_size_bytes")
                or rom_detail.get("filesize")
                or rom_detail.get("file_size")
                or rom_detail.get("bytes")
                or rom_detail.get("size")
            )
            if not size_val and isinstance(rom_detail.get("files"), list) and rom_detail["files"]:
                calc_size = 0
                for f_item in rom_detail["files"]:
                    if isinstance(f_item, dict):
                        calc_size += (
                            f_item.get("file_size_bytes")
                            or f_item.get("file_size")
                            or f_item.get("size_bytes")
                            or f_item.get("bytes")
                            or f_item.get("size")
                            or 0
                        )
                if calc_size > 0:
                    size_val = calc_size

            self.file_size = int(size_val) if size_val else 0

        if self.file_size == 0 and self.rom_id:
            try:
                head_size = client.get_rom_file_size(self.rom_id, self.file_name)
                if head_size > 0:
                    self.file_size = head_size
            except Exception as e:
                logger.debug("Failed fetching HEAD size for rom_id %s: %s", self.rom_id, e)

        local_path = self.file_resolver.resolve_local_rom(
            rom_id=self.rom_id,
            rom_name=self.rom_name,
            file_name=self.file_name,
            platform_slug=self.platform_slug,
            download_dir=self.settings.download_dir,
        )

        if local_path and local_path.exists():
            self.local_file_path = str(local_path)
            self._safe_after(0, self._show_ready_to_launch_state)
        else:
            self._safe_after(0, self._show_prompt_install_state)

    def _show_prompt_install_state(self) -> None:
        """Update UI when ROM is missing locally and prompt user to install."""
        self.title_label.configure(text=self.rom_name)
        self.platform_badge.configure(text=self.platform_slug.upper() if self.platform_slug else "ROMM")

        display_filename = Path(self.file_name).name if self.file_name else f"{self.rom_name}"
        formatted_size = format_size(self.file_size)
        detail_text = f"This ROM is not yet downloaded on your system.\n\nFile Name:  {display_filename}\nFile Size:   {formatted_size}"

        self.status_card.set_status(
            title="ROM Not Found Locally",
            detail=detail_text,
            title_color=COLOR_WARNING,
            detail_color=COLOR_TEXT,
        )
        self.status_card.configure_cancel_button(text="Cancel", command=self.destroy)
        self.status_card.configure_action_button(
            text="Install ROM",
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            state="normal",
            command=self._start_download,
        )
        self.status_card.show_action_frame()

    def _show_ready_to_launch_state(self) -> None:
        """Update UI when ROM is present on local system and prepare for launch."""
        self.title_label.configure(text=self.rom_name)
        self.platform_badge.configure(text=self.platform_slug.upper() if self.platform_slug else "ROMM")

        display_path = self.local_file_path or "Local disk"
        self.status_card.set_status(
            title="Ready to Launch",
            detail=f"Game is available locally.\nLocation: {display_path}\n\nChecking save data...",
            title_color=COLOR_SUCCESS,
            detail_color=COLOR_TEXT,
        )
        self.status_card.hide_action_button()
        self.status_card.configure_cancel_button(text="Cancel", command=self._cancel_auto_launch)
        self.status_card.show_action_frame()

        self.auto_launch_timer = threading.Timer(1.2, self._execute_launch)
        self.auto_launch_timer.start()

    def _cancel_auto_launch(self) -> None:
        """Cancel auto-launch timer and show Launch Now button."""
        if self.auto_launch_timer:
            self.auto_launch_timer.cancel()
            self.auto_launch_timer = None
        logger.info("Auto-launch cancelled by user for rom_id %s", self.rom_id)

        self.status_card.set_status(
            title="Launch Cancelled",
            detail=f"Auto-launch cancelled.\nGame location: {self.local_file_path}",
            title_color=COLOR_WARNING,
        )
        self.status_card.configure_cancel_button(text="Close", command=self.destroy)
        self.status_card.configure_action_button(
            text="Launch Now",
            fg_color=COLOR_INFO_HOVER,
            hover_color=COLOR_INFO,
            state="normal",
            command=self._execute_launch,
        )

    def _start_download(self) -> None:
        """Handle download button click and initiate streaming download."""
        if self.is_downloading:
            return

        self._clear_error_state()
        self.is_downloading = True
        logger.info("Initiating on-demand ROM download for rom_id %s", self.rom_id)
        self.status_card.set_status(
            title="Downloading ROM...",
            detail="Connecting to server...",
            title_color=COLOR_INFO_HOVER,
        )
        self.status_card.configure_action_button(text="Downloading...", command=None, state="disabled")
        self.status_card.configure_cancel_button(state="disabled")
        self.status_card.show_progress_bar(mode="determinate")

        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self) -> None:
        """Worker thread for downloading ROM content."""
        def progress_callback(pct: float, msg: str) -> None:
            self._safe_after(0, lambda: self._update_download_progress(pct, msg))

        success, final_path, error_msg = self.download_service.download_rom(
            rom_id=self.rom_id,
            rom_name=self.rom_name,
            file_name=self.file_name,
            platform_slug=self.platform_slug,
            download_dir=self.settings.download_dir,
            romm_url=self.settings.romm_url,
            api_key=self.settings.api_key,
            progress_callback=progress_callback,
        )

        if success and final_path:
            self.local_file_path = str(final_path)
            self._safe_after(0, self._on_download_complete)
        else:
            self._safe_after(0, lambda: self._on_download_failed(error_msg))

    def _update_download_progress(self, pct: float, status_text: str) -> None:
        """Update progress bar and detail text during download."""
        self.status_card.set_progress(pct, status_text)

    def _on_download_complete(self) -> None:
        """Update UI state on successful download."""
        self.is_downloading = False
        self.status_card.set_progress(1.0)
        self.status_card.set_status(
            title="Download Complete!",
            detail=f"ROM installed to:\n{self.local_file_path}",
            title_color=COLOR_SUCCESS,
        )
        self.status_card.configure_cancel_button(text="Close", command=self.destroy, state="normal")
        self.status_card.configure_action_button(
            text="Launch ROM",
            fg_color=COLOR_INFO_HOVER,
            hover_color=COLOR_INFO,
            state="normal",
            command=self._execute_launch,
        )

    def _on_download_failed(self, error_message: Optional[str] = None) -> None:
        """Update UI state on failed download."""
        self.is_downloading = False
        msg = error_message or "Could not download ROM file from RomM server. Please check your connection."
        self._show_error_state(
            title="Download Failed",
            message=msg,
            full_details=msg,
            retry_command=self._start_download,
            retry_text="Retry Download",
        )

    def _execute_launch(self) -> None:
        """Initiate pre-launch save sync and RetroArch execution flow."""
        self._clear_error_state()
        if self.auto_launch_timer:
            self.auto_launch_timer.cancel()
            self.auto_launch_timer = None

        if not self.local_file_path or not Path(self.local_file_path).exists():
            logger.error("Cannot launch: ROM file path '%s' does not exist", self.local_file_path)
            self._show_error_state(
                title="Error",
                message="ROM file path does not exist on disk.",
                full_details=f"ROM file path does not exist on disk:\n{self.local_file_path}",
            )
            return

        logger.info("Executing launch sequence for rom_id %s (%s)", self.rom_id, self.rom_name)
        if not getattr(self.settings, "save_sync_enabled", True):
            action, msg, remote_save, default_target = self.save_coordinator.sync_pre_launch(
                rom_id=self.rom_id,
                local_file_path=str(self.local_file_path),
                platform_slug=self.platform_slug,
            )
            self._launch_retroarch_process(default_target)
            return

        self.status_card.set_status(
            title="Syncing Save Data...",
            detail="Checking RomM server for save data...",
            title_color=COLOR_INFO_HOVER,
        )
        self.status_card.hide_action_button()
        self.status_card.configure_cancel_button(state="disabled")

        threading.Thread(target=self._pre_launch_sync_worker, daemon=True).start()

    def _pre_launch_sync_worker(self) -> None:
        """Worker thread executing pre-launch save sync."""
        action, msg, remote_save, save_target = self.save_coordinator.sync_pre_launch(
            rom_id=self.rom_id,
            local_file_path=str(self.local_file_path),
            platform_slug=self.platform_slug,
        )

        if action == "CONFLICT":
            logger.info("Pre-launch save sync conflict detected for rom_id %s", self.rom_id)
            self._safe_after(0, lambda: self._on_sync_conflict(remote_save, save_target or Path("")))
        elif action == "UNREACHABLE":
            self._safe_after(0, self._on_server_unreachable)
        else:
            self._safe_after(0, lambda: self._launch_retroarch_process(save_target))

    def _on_server_unreachable(self) -> None:
        """Prompt user when RomM server is unreachable."""
        self.status_card.set_status(
            title="RomM Server Unreachable",
            detail="Could not connect to RomM server to sync save data.\n\nWould you like to launch the game anyway or cancel?",
            title_color=COLOR_WARNING,
            detail_color=COLOR_TEXT,
        )
        core_name = (
            self.settings.core_mappings.get(self.platform_slug)
            or DEFAULT_CORE_MAPPINGS.get(self.platform_slug, "")
        )
        _, default_target = find_local_save_file(
            str(self.local_file_path),
            platform_slug=self.platform_slug,
            configured_retroarch_path=self.settings.retroarch_path,
            core_name=core_name,
        )

        self.status_card.configure_cancel_button(state="normal", text="Cancel", command=self.destroy)
        self.status_card.configure_action_button(
            text="Continue Launch",
            fg_color=COLOR_INFO_HOVER,
            hover_color=COLOR_INFO,
            state="normal",
            command=lambda: self._launch_retroarch_process(default_target),
        )
        self.status_card.show_action_frame()

    def _on_sync_conflict(self, remote_save: Optional[Dict[str, Any]], save_target: Path) -> None:
        """Prompt user to choose save version when conflict occurs."""
        self.status_card.set_status(
            title="Save Conflict Detected",
            detail="Save data exists both locally and on RomM, but they differ.\n\nWhich save version would you like to use?",
            title_color=COLOR_WARNING,
            detail_color=COLOR_TEXT,
        )
        self.status_card.configure_cancel_button(
            state="normal",
            text="Use Remote Save",
            fg_color=COLOR_PURPLE,
            hover_color=COLOR_PURPLE_HOVER,
            command=lambda: self._resolve_conflict_choice("remote", remote_save, save_target),
        )
        self.status_card.configure_action_button(
            state="normal",
            text="Use Local Save",
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            command=lambda: self._resolve_conflict_choice("local", remote_save, save_target),
        )
        self.status_card.show_action_frame()

    def _resolve_conflict_choice(self, choice: str, remote_save: Optional[Dict[str, Any]], save_target: Path) -> None:
        """Handle user choice for conflict resolution."""
        logger.info("User selected conflict resolution choice: %s", choice)
        self.status_card.set_status(
            title="Applying Save Choice...",
            detail=f"Applying selected save option: {choice.upper()}...",
            title_color=COLOR_INFO_HOVER,
        )
        self.status_card.configure_action_button(state="disabled", text="Please Wait...", command=None)
        self.status_card.configure_cancel_button(state="disabled")

        threading.Thread(
            target=self._conflict_worker,
            args=(choice, remote_save, save_target),
            daemon=True,
        ).start()

    def _conflict_worker(self, choice: str, remote_save: Optional[Dict[str, Any]], save_target: Path) -> None:
        """Worker thread applying chosen save conflict option."""
        res_target = self.save_coordinator.resolve_conflict_choice(
            choice=choice,
            rom_id=self.rom_id,
            remote_save=remote_save,
            save_target=save_target,
            platform_slug=self.platform_slug,
        )
        self._safe_after(0, lambda: self._launch_retroarch_process(res_target))

    def _launch_retroarch_process(self, save_target: Optional[Path]) -> None:
        """Launch RetroArch process, minimize window, and monitor process."""
        self.status_card.set_status(
            title="Launching RetroArch...",
            detail=f"Starting game: {self.rom_name}",
            title_color=COLOR_INFO_HOVER,
        )
        self.status_card.hide_action_button()

        success, msg, proc = self.process_supervisor.launch_game(
            rom_path=str(self.local_file_path),
            platform_slug=self.platform_slug,
            configured_retroarch_path=self.settings.retroarch_path,
            custom_mappings=self.settings.core_mappings,
        )

        if success and proc:
            logger.info("Successfully launched RetroArch process PID %s: %s", proc.pid, msg)
            self.is_game_running = True
            self.session_start_time = datetime.now(timezone.utc)
            self.session_start_mono = time.monotonic()

            self.status_card.set_status(
                title=f"{self.rom_name} is currently running, do not close this window",
                detail=(
                    "Game session active. Save data will automatically sync when you exit."
                    if getattr(self.settings, "save_sync_enabled", True)
                    else "Game session active. Launcher will close when you exit."
                ),
                title_color=COLOR_SUCCESS,
                detail_color=COLOR_TEXT,
            )
            self.status_card.show_progress_bar(mode="indeterminate")

            self._clear_topmost()
            self.iconify()

            if getattr(proc, "pid", None):
                self.process_supervisor.spawn_focus_worker(proc.pid)

            threading.Thread(
                target=self._monitor_process_worker,
                args=(proc, save_target),
                daemon=True,
            ).start()
        else:
            logger.error("RetroArch process launch failed: %s", msg)
            self._show_error_state(
                title="Launch Failed",
                message=msg,
                full_details=msg,
                retry_command=self._execute_launch,
                retry_text="Retry Launch",
            )

    def _monitor_process_worker(self, proc: Any, save_target: Optional[Path]) -> None:
        """Wait for emulator process to exit and dispatch callbacks."""
        self.process_supervisor.monitor_process(
            proc=proc,
            save_target=save_target,
            session_start_mono=self.session_start_mono,
            session_start_time=self.session_start_time,
            on_error=lambda ret, stderr: self._safe_after(0, lambda: self._on_retroarch_error(ret, stderr)),
            on_exit=lambda target: self._safe_after(0, lambda: self._on_retroarch_exit(target)),
        )

    def _on_retroarch_error(self, returncode: int, stderr_lines: List[str]) -> None:
        """Restore launcher window and display failure message for non-zero exit."""
        self.is_game_running = False
        self.status_card.hide_progress_bar()

        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self._safe_after(500, self._clear_topmost)
        except Exception as e:
            logger.debug("Failed bringing window to foreground after launch error: %s", e)

        title = f"Launch Failed (Exit Code {returncode})"
        error_msg = f"RetroArch exited unexpectedly with return code {returncode}."
        non_benign = self.process_supervisor.filter_stderr_lines(stderr_lines)
        if non_benign:
            error_msg += f"\n{non_benign[-1]}"

        detailed_lines = non_benign if non_benign else stderr_lines
        full_details = (
            f"RetroArch exited unexpectedly with return code {returncode}.\n\n"
            f"Standard Error:\n" + "\n".join(detailed_lines)
        )

        self._show_error_state(
            title=title,
            message=error_msg,
            full_details=full_details,
            retry_command=self._execute_launch,
            retry_text="Retry Launch",
        )

    def _on_retroarch_exit(self, save_target: Optional[Path]) -> None:
        """Restore window to foreground and perform post-launch save upload."""
        self.is_game_running = False
        self.status_card.hide_progress_bar()

        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self._safe_after(500, self._clear_topmost)
        except Exception as e:
            logger.debug("Failed bringing window to foreground after game exit: %s", e)

        save_sync_enabled = getattr(self.settings, "save_sync_enabled", True)
        if save_sync_enabled:
            self.status_card.set_status(
                title="Uploading Save to RomM...",
                detail="Game closed. Uploading save file back to RomM server...",
                title_color=COLOR_INFO_HOVER,
            )
        else:
            self.status_card.set_status(
                title="Session Complete",
                detail="Game closed.",
                title_color=COLOR_SUCCESS,
            )

        threading.Thread(
            target=self._post_launch_upload_worker,
            args=(save_target,),
            daemon=True,
        ).start()

    def _post_launch_upload_worker(self, save_target: Optional[Path]) -> None:
        """Worker thread uploading save file and recording playtime session."""
        try:
            self.save_coordinator.sync_post_launch(
                rom_id=self.rom_id,
                local_file_path=self.local_file_path,
                platform_slug=self.platform_slug,
                save_target=save_target,
                session_start_time=self.session_start_time,
                session_start_mono=self.session_start_mono,
            )
        finally:
            self._safe_after(0, self._on_post_launch_complete)

    def _on_post_launch_complete(self) -> None:
        """Show post-launch completion message and close window."""
        logger.info("Post-launch execution sequence finished for rom_id %s. Closing launcher window.", self.rom_id)
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self._safe_after(500, self._clear_topmost)
        except Exception as e:
            logger.debug("Failed bringing window to foreground on completion: %s", e)

        save_sync_enabled = getattr(self.settings, "save_sync_enabled", True)
        if save_sync_enabled:
            self.status_card.set_status(
                title="Save Upload Complete!",
                detail="Save file successfully uploaded to RomM server.",
                title_color=COLOR_SUCCESS,
            )
            self._safe_after(1500, self.destroy)
        else:
            self.status_card.set_status(
                title="Session Complete",
                detail="Game closed.",
                title_color=COLOR_SUCCESS,
            )
            self._safe_after(1000, self.destroy)
