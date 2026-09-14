"""Installed ROMs Library GUI View."""

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tkinter as tk
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk
from PIL import Image

from romm_steam_sync.adapters.retroarch.base import clean_subprocess_env
from romm_steam_sync.adapters.steam_path import SteamPathResolver
from romm_steam_sync.adapters.wrapper_installer import (
    get_installed_wrapper_path,
    resolve_pythonw_executable,
)
from romm_steam_sync.config import AppSettings
from romm_steam_sync.domain import (
    Rom,
    RomInstall,
    detect_launch_file,
    sanitize_title,
    titles_match,
)
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.service_layer.sync_service import (
    normalize_platform_identifier,
)
from romm_steam_sync.ui.components.game_detail_modal import GameDetailModal

logger = logging.getLogger(__name__)

TILE_WIDTH = 125
TILE_HEIGHT = 185

# Aliases for backwards-compatibility within module and tests
_sanitize_title = sanitize_title
_titles_match = titles_match


class LibraryGameTile(ctk.CTkFrame):
    """Grid tile widget representing an installed ROM game."""

    def __init__(
        self,
        parent,
        rom_id: int,
        rom_name: str,
        platform_slug: str,
        file_path: str,
        cover_path: Optional[str] = None,
        on_click: Optional[Callable[[], None]] = None,
    ):
        super().__init__(
            parent,
            width=TILE_WIDTH,
            height=TILE_HEIGHT,
            corner_radius=8,
            fg_color="#1a202c",
            border_width=1,
            border_color="#2d3748",
        )
        self.rom_id = rom_id
        self.rom_name = rom_name
        self.platform_slug = platform_slug
        self.file_path = file_path
        self.cover_path = cover_path
        self.on_click = on_click
        self.fallback_label: Optional[ctk.CTkLabel] = None

        self.pack_propagate(False)
        self.grid_propagate(False)

        # Image Container Frame
        self.img_frame = ctk.CTkFrame(self, width=TILE_WIDTH - 8, height=140, fg_color="#12161f", corner_radius=6)
        self.img_frame.pack(padx=4, pady=(4, 2), fill="both", expand=True)
        self.img_frame.pack_propagate(False)

        loaded_image_label = False
        self._ctk_image: Optional[ctk.CTkImage] = None
        self._tk_image: Optional[tk.PhotoImage] = None

        if cover_path and Path(cover_path).exists():
            try:
                pil_img = Image.open(cover_path)
                pil_img.load()
                self._ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(TILE_WIDTH - 12, 135))
                self.cover_widget = ctk.CTkLabel(self.img_frame, image=self._ctk_image, text="")
                self.cover_widget.pack(fill="both", expand=True)
                loaded_image_label = True
            except (ImportError, ModuleNotFoundError) as e:
                logger.warning(
                    "Pillow Tkinter support (_imagingtk) unavailable for tile cover %s: %s. Falling back to native Tk PhotoImage.",
                    cover_path,
                    e,
                )
                try:
                    self._tk_image = tk.PhotoImage(file=cover_path)
                    lbl_img = tk.Label(self.img_frame, image=self._tk_image, bg="#12161f", bd=0)
                    lbl_img.pack(fill="both", expand=True)
                    self.cover_widget = lbl_img
                    loaded_image_label = True
                except Exception as tk_err:
                    logger.debug("Native PhotoImage fallback failed for %s: %s", cover_path, tk_err)
            except Exception as e:
                logger.warning("Could not open/render cover image for tile %s: %s", cover_path, e)

        if not loaded_image_label:
            self.fallback_label = ctk.CTkLabel(
                self.img_frame,
                text=rom_name[:12] + "..." if len(rom_name) > 14 else rom_name,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#a0aec0",
            )
            self.fallback_label.pack(expand=True)
            self.cover_widget = self.fallback_label

        # Game Title Label
        truncated_name = rom_name if len(rom_name) <= 15 else rom_name[:13] + "..."
        self.name_lbl = ctk.CTkLabel(
            self,
            text=truncated_name,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#edf2f7",
        )
        self.name_lbl.pack(padx=4, pady=(2, 4), side="bottom")

        # Bind click handlers across all tile sub-widgets
        if on_click:
            for w in (self, self.img_frame, self.cover_widget, self.name_lbl):
                w.bind("<Button-1>", lambda e: on_click())

        # Bind hover events across all tile sub-widgets for seamless propagation
        for w in (self, self.img_frame, self.cover_widget, self.name_lbl):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def _is_mouse_inside(self, event) -> bool:
        """Check if mouse pointer is still inside the tile or any of its descendant widgets."""
        if event is None:
            return False
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
            curr = w
            while curr is not None:
                if curr == self:
                    return True
                parent = getattr(curr, "master", None)
                if parent is None:
                    parent = getattr(curr, "_parent", None)
                curr = parent
        except Exception as e:
            logger.debug("Failed checking mouse containing widget: %s", e)
        return False

    def _on_enter(self, event=None):
        """Highlight tile background, border, cover container, and title text when hovered."""
        self.configure(border_color="#4299e1", fg_color="#2b374e")
        self.img_frame.configure(fg_color="#1a202c")
        self.name_lbl.configure(text_color="#63b3ed")
        if self.fallback_label:
            self.fallback_label.configure(text_color="#63b3ed")

    def _on_leave(self, event=None):
        """Restore default dark tile appearance when mouse leaves tile boundary."""
        if event and self._is_mouse_inside(event):
            return
        self.configure(border_color="#2d3748", fg_color="#1a202c")
        self.img_frame.configure(fg_color="#12161f")
        self.name_lbl.configure(text_color="#edf2f7")
        if self.fallback_label:
            self.fallback_label.configure(text_color="#a0aec0")


class LibraryView(ctk.CTkFrame):
    """Desktop GUI View displaying installed local ROMs grouped by platform."""

    def __init__(self, parent, settings: AppSettings, on_navigate_tab: Optional[Callable[[str], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.settings = settings
        self.on_navigate_tab = on_navigate_tab
        self.db_session = DatabaseSession()

        self.installed_games: List[Dict[str, Any]] = []
        self._current_col_count: Optional[int] = None
        self._resize_timer: Optional[str] = None
        self._detail_modal: Optional[GameDetailModal] = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_content_area()

        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, event=None) -> None:
        """Handle frame resize events to dynamically update grid column layout when column count changes.

        Args:
            event: Optional Tkinter event object from <Configure> binding.
        """
        valid_widgets = (self, getattr(self, "_canvas", None))
        if event is not None and event.widget not in valid_widgets:
            return
        if self._resize_timer is not None:
            try:
                self.after_cancel(self._resize_timer)
            except Exception as e:
                logger.debug("Failed to cancel resize timer: %s", e)
            self._resize_timer = None
        self._resize_timer = self.after(100, self._check_col_count_and_render)

    def _check_col_count_and_render(self) -> None:
        """Evaluate column count and re-render grid if width threshold changed."""
        self._resize_timer = None
        col_count = self._get_col_count()
        if self._current_col_count is None or col_count != self._current_col_count:
            logger.debug(
                "LibraryView width changed; re-rendering layout (%s cols -> %d cols).",
                str(self._current_col_count),
                col_count,
            )
            self._filter_and_render()

    def _get_effective_width(self) -> int:
        """Get effective available width of LibraryView, handling initial unmapped state where winfo_width() returns <= 200.

        Returns:
            Effective pixel width available for grid calculations, defaulting to 800 if unmapped.
        """
        w = self.winfo_width()
        if w <= 200 and hasattr(self, "scroll_frame"):
            try:
                w = self.scroll_frame.winfo_width()
            except Exception:
                w = 0
        if w <= 200 and self.master:
            try:
                w = self.master.winfo_width()
            except Exception:
                w = 0
        if w <= 200:
            try:
                w = self.winfo_toplevel().winfo_width()
            except Exception:
                w = 0
        if w <= 200:
            w = 800
        return w

    def _get_col_count(self) -> int:
        """Calculate number of columns for grid layout based on effective available width."""
        width = self._get_effective_width()
        return max(1, width // (TILE_WIDTH + 15))

    def _build_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Local ROM Library",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        self.stats_badge = ctk.CTkLabel(
            header_frame,
            text="0 Installed ROMs",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2b6cb0",
            text_color="#ebf8ff",
            corner_radius=6,
            padx=10,
            pady=4,
        )
        self.stats_badge.grid(row=0, column=1, sticky="w", padx=15)

        # Search Bar
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._filter_and_render())
        self.search_entry = ctk.CTkEntry(
            header_frame,
            textvariable=self.search_var,
            placeholder_text="Search installed ROMs...",
            width=220,
            height=32,
        )
        self.search_entry.grid(row=0, column=2, sticky="e", padx=(0, 10))

        # Refresh Button
        refresh_btn = ctk.CTkButton(
            header_frame,
            text="Refresh",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=90,
            height=32,
            fg_color="#4a5568",
            hover_color="#2d3748",
            command=self.refresh,
        )
        refresh_btn.grid(row=0, column=3, sticky="e")

    def _build_content_area(self):
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="#12161f",
            corner_radius=10,
            border_width=1,
            border_color="#2d3748",
        )
        self.scroll_frame.grid(row=1, column=0, padx=10, pady=(5, 10), sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    def refresh(self):
        """Fetch installed ROMs from DB and local storage and re-render grid."""
        logger.info("Refreshing local installed ROM library view...")
        self.load_installed_games()
        self._filter_and_render()

    def load_installed_games(self):
        """Scan SQLite database and local download directory for installed ROMs, handling deduplication."""
        self.installed_games.clear()

        config_dir, _ = SteamPathResolver.get_user_config_dir(
            user_id=self.settings.steam_user_id,
            custom_steam_path=self.settings.steam_custom_path,
        )
        grid_dir = config_dir / "grid" if config_dir else None

        installed_rom_ids = set()
        installed_file_paths = set()

        with self.db_session as db:
            all_known_roms = {r.rom_id: r for r in db.roms.list_all()}

            # 1. Load registered installs from SQLite
            installs = db.installs.list_all()
            for install in installs:
                p_path = Path(install.file_path)
                p_path_resolved = str(p_path.resolve()).lower() if p_path.exists() else str(p_path).lower()

                # Clean up / skip duplicate install records in db.installs
                if install.rom_id in installed_rom_ids or p_path_resolved in installed_file_paths:
                    logger.info("Cleaning up duplicate RomInstall record in DB for rom_id %s (file: %s)", install.rom_id, p_path)
                    try:
                        db.installs.delete(install.rom_id)
                        db.commit()
                    except Exception as e:
                        logger.warning("Could not delete duplicate RomInstall record %s: %s", install.rom_id, e)
                    continue

                if p_path.exists():
                    rom_entity = db.roms.get(install.rom_id)
                    rom_name = rom_entity.name if rom_entity else p_path.stem

                    # Detect if this record was auto-registered under a wrong rom_id from prior loose matching bug
                    if rom_entity and rom_entity.name and not _titles_match(rom_entity.name, p_path.stem):
                        logger.info(
                            "Detected mismatched RomInstall record (rom_id: %s '%s' vs file: '%s'). Cleaning up.",
                            install.rom_id,
                            rom_entity.name,
                            p_path.name,
                        )
                        try:
                            db.installs.delete(install.rom_id)
                            db.commit()
                        except Exception as e:
                            logger.warning("Could not delete mismatched RomInstall record %s: %s", install.rom_id, e)
                        continue

                    platform_slug = rom_entity.platform_slug if rom_entity else "romm"
                    shortcut_app_id = rom_entity.shortcut_app_id if rom_entity else None
                    cover_url = rom_entity.cover_url if rom_entity else None

                    cover_path = self._resolve_cover_path(
                        rom_id=install.rom_id,
                        shortcut_app_id=shortcut_app_id,
                        cover_url=cover_url,
                        grid_dir=grid_dir,
                    )

                    self.installed_games.append({
                        "rom_id": install.rom_id,
                        "name": rom_name,
                        "platform_slug": platform_slug,
                        "file_path": str(p_path),
                        "cover_path": cover_path,
                        "installed_at": install.installed_at,
                    })
                    installed_rom_ids.add(install.rom_id)
                    installed_file_paths.add(p_path_resolved)

            # 2. Scan download_dir for unindexed local ROM files and subdirectories that match DB records
            download_dir = Path(self.settings.download_dir)
            if download_dir.exists():
                for p_folder in download_dir.iterdir():
                    if p_folder.is_dir():
                        p_slug = p_folder.name.lower()
                        for item in p_folder.iterdir():
                            target_file: Optional[Path] = None
                            item_dir: Optional[Path] = p_folder
                            match_stem: str = ""

                            if item.is_file():
                                target_file = item
                                match_stem = item.stem
                                item_dir = p_folder
                            elif item.is_dir():
                                # Dedicated game subdirectory
                                sub_files = [f for f in item.rglob("*") if f.is_file()]
                                if sub_files:
                                    target_file = detect_launch_file(sub_files, preferred_stem=item.name)
                                    match_stem = item.name
                                    item_dir = item

                            if not target_file:
                                continue

                            f_path_resolved = str(target_file.resolve()).lower()
                            if f_path_resolved in installed_file_paths:
                                continue

                            # Check if file/directory corresponds to an unindexed known Rom record
                            matched_rom: Optional[Rom] = None
                            for r_item in all_known_roms.values():
                                if r_item.rom_id not in installed_rom_ids:
                                    if r_item.fs_name and (
                                        r_item.fs_name.lower() == target_file.name.lower()
                                        or Path(r_item.fs_name).stem.lower() == match_stem.lower()
                                    ):
                                        matched_rom = r_item
                                        break
                                    elif r_item.name and (
                                        _titles_match(r_item.name, match_stem)
                                        or _titles_match(r_item.name, target_file.stem)
                                    ):
                                        matched_rom = r_item
                                        break

                            if matched_rom:
                                cover_path = self._resolve_cover_path(
                                    rom_id=matched_rom.rom_id,
                                    shortcut_app_id=matched_rom.shortcut_app_id,
                                    cover_url=matched_rom.cover_url,
                                    grid_dir=grid_dir,
                                )
                                self.installed_games.append({
                                    "rom_id": matched_rom.rom_id,
                                    "name": matched_rom.name,
                                    "platform_slug": matched_rom.platform_slug or p_slug,
                                    "file_path": str(target_file),
                                    "cover_path": cover_path,
                                    "installed_at": None,
                                })
                                installed_rom_ids.add(matched_rom.rom_id)
                                installed_file_paths.add(f_path_resolved)

                                # Auto-register in db.installs
                                try:
                                    db.installs.add(
                                        RomInstall(
                                            rom_id=matched_rom.rom_id,
                                            file_path=str(target_file),
                                            rom_dir=str(item_dir),
                                            launchable=True,
                                            installed_at=datetime.now(timezone.utc),
                                        )
                                    )
                                    db.commit()
                                except Exception as e:
                                    logger.warning("Failed auto-registering RomInstall for %s: %s", matched_rom.rom_id, e)

        logger.info("Loaded %d installed games in library.", len(self.installed_games))

    def _resolve_cover_path(
        self,
        rom_id: int,
        shortcut_app_id: Optional[int],
        cover_url: Optional[str],
        grid_dir: Optional[Path],
    ) -> Optional[str]:
        """Find local artwork image file for game cover across grid and cache directories."""
        from romm_steam_sync.config import get_default_config_dir

        covers_dir = get_default_config_dir() / "covers"

        # 1. Check Steam grid directory if shortcut_app_id is bound
        if grid_dir and grid_dir.exists() and shortcut_app_id:
            app_id_candidates = [
                str(shortcut_app_id & 0xFFFFFFFF),  # Unsigned 32-bit (e.g. 3482900548)
                str(shortcut_app_id),               # Signed 32-bit (e.g. -812066748)
                str(((shortcut_app_id & 0xFFFFFFFF) << 32) | 0x02000000),  # Unsigned 64-bit
            ]
            suffixes = ["p.png", ".png", "p.jpg", ".jpg", "_hero.png", "_logo.png"]
            for app_id_str in app_id_candidates:
                for suffix in suffixes:
                    cand = grid_dir / f"{app_id_str}{suffix}"
                    if cand.exists():
                        return str(cand)

        # 2. Check local covers cache directory
        if covers_dir.exists():
            for suffix in ["p.png", ".png", "p.jpg", ".jpg"]:
                cand = covers_dir / f"{rom_id}{suffix}"
                if cand.exists():
                    return str(cand)

        # 3. On-demand download from RomM API if configured
        if self.settings.romm_url and rom_id:
            try:
                from romm_steam_sync.adapters.romm_api import RomMApiClient
                covers_dir.mkdir(parents=True, exist_ok=True)
                target_cover = covers_dir / f"{rom_id}p.png"
                client = RomMApiClient(
                    base_url=self.settings.romm_url,
                    api_key=self.settings.api_key,
                )
                success = client.download_cover(rom_id, str(target_cover), cover_url)
                if success and target_cover.exists():
                    return str(target_cover)
            except Exception as e:
                logger.debug("On-demand cover download failed for rom_id %s: %s", rom_id, e)

        return None

    def _filter_and_render(self):
        """Filter games list based on search query and render sectioned grid."""
        for child in self.scroll_frame.winfo_children():
            child.destroy()

        query = self.search_var.get().strip().lower()
        if query:
            filtered = [g for g in self.installed_games if query in g["name"].lower() or query in g["platform_slug"].lower()]
        else:
            filtered = list(self.installed_games)

        total_count = len(filtered)
        self.stats_badge.configure(text=f"{total_count} Installed Game{'s' if total_count != 1 else ''}")

        if not filtered:
            self._render_empty_state(has_search_query=bool(query))
            return

        # Group games by platform
        platform_groups: Dict[str, List[Dict[str, Any]]] = {}
        for game in filtered:
            p_slug = game["platform_slug"]
            canonical_key, display_name = normalize_platform_identifier(p_slug)
            if display_name not in platform_groups:
                platform_groups[display_name] = []
            platform_groups[display_name].append(game)

        # Sort platforms alphabetically
        sorted_platforms = sorted(platform_groups.keys())

        row_idx = 0
        for p_name in sorted_platforms:
            games_in_p = sorted(platform_groups[p_name], key=lambda x: x["name"].lower())

            # Section Header
            sec_header = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            sec_header.grid(row=row_idx, column=0, padx=10, pady=(15, 8), sticky="ew")
            sec_header.grid_columnconfigure(1, weight=1)

            lbl_pname = ctk.CTkLabel(
                sec_header,
                text=p_name,
                font=ctk.CTkFont(size=16, weight="bold"),
                text_color="#63b3ed",
            )
            lbl_pname.grid(row=0, column=0, sticky="w")

            badge_count = ctk.CTkLabel(
                sec_header,
                text=f"{len(games_in_p)} game{'s' if len(games_in_p) != 1 else ''}",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#2d3748",
                text_color="#a0aec0",
                corner_radius=4,
                padx=8,
                pady=2,
            )
            badge_count.grid(row=0, column=1, sticky="w", padx=10)

            # Flow grid container frame
            grid_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            grid_container.grid(row=row_idx + 1, column=0, padx=10, pady=(0, 10), sticky="ew")

            # Pack tiles into grid container with wrapping
            col_count = self._get_col_count()
            self._current_col_count = col_count
            for g_idx, game_item in enumerate(games_in_p):
                r = g_idx // col_count
                c = g_idx % col_count
                tile = LibraryGameTile(
                    grid_container,
                    rom_id=game_item["rom_id"],
                    rom_name=game_item["name"],
                    platform_slug=game_item["platform_slug"],
                    file_path=game_item["file_path"],
                    cover_path=game_item["cover_path"],
                    on_click=lambda item=game_item: self._open_detail_modal(item),
                )
                tile.grid(row=r, column=c, padx=8, pady=8, sticky="nw")

            row_idx += 2

    def _render_empty_state(self, has_search_query: bool):
        """Render empty state screen when no games match."""
        empty_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        empty_frame.grid(row=0, column=0, pady=60, sticky="ew")
        empty_frame.grid_columnconfigure(0, weight=1)

        if has_search_query:
            title_lbl = ctk.CTkLabel(
                empty_frame,
                text="No ROMs Found",
                font=ctk.CTkFont(size=18, weight="bold"),
            )
            title_lbl.grid(row=0, column=0, pady=(0, 5))

            desc_lbl = ctk.CTkLabel(
                empty_frame,
                text="No installed games match your search query.",
                font=ctk.CTkFont(size=13),
                text_color="#a0aec0",
            )
            desc_lbl.grid(row=1, column=0)
        else:
            self.empty_msg_label = ctk.CTkLabel(
                empty_frame,
                text="No games are installed, open Steam to install and play games.",
                font=ctk.CTkFont(size=16),
                text_color="#a0aec0",
            )
            self.empty_msg_label.grid(row=0, column=0)

    def _open_detail_modal(self, game_item: Dict[str, Any]):
        """Open game detail modal for selected game tile."""
        logger.info("Opening detail modal for game: %s (rom_id: %s)", game_item["name"], game_item["rom_id"])
        if (
            self._detail_modal is not None
            and hasattr(self._detail_modal, "winfo_exists")
            and self._detail_modal.winfo_exists()
        ):
            self._detail_modal.lift()
            self._detail_modal.focus()
            return

        try:
            self._detail_modal = GameDetailModal(
                self,
                rom_id=game_item["rom_id"],
                rom_name=game_item["name"],
                platform_slug=game_item["platform_slug"],
                file_path=game_item["file_path"],
                cover_path=game_item["cover_path"],
                on_launch=self._launch_game,
                on_uninstall=self._uninstall_game,
            )
        except Exception as e:
            logger.error(
                "Failed to open GameDetailModal for rom_id %s: %s",
                game_item.get("rom_id"),
                e,
                exc_info=True,
            )

    def _launch_game(self, rom_id: int, platform_slug: str):
        """Launch selected ROM using wrapper or launcher CLI entry point."""
        logger.info("Initiating game launch from Library for rom_id %s (platform: %s)", rom_id, platform_slug)
        wrapper_path = get_installed_wrapper_path()
        py_exe = resolve_pythonw_executable()

        if wrapper_path.exists():
            if sys.platform == "win32" and wrapper_path.suffix == ".vbs":
                cmd = ["wscript.exe", str(wrapper_path), "--rom-id", str(rom_id), "--platform", platform_slug]
            else:
                cmd = [str(wrapper_path), "--rom-id", str(rom_id), "--platform", platform_slug]
        else:
            cmd = [py_exe, "-m", "romm_steam_sync.launcher", "--rom-id", str(rom_id), "--platform", platform_slug]

        try:
            logger.info("Executing launcher subprocess command: %s", cmd)
            clean_env = clean_subprocess_env()
            if sys.platform == "win32":
                creation_flags = (
                    subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                )  # type: ignore
                subprocess.Popen(cmd, creationflags=creation_flags, env=clean_env)
            else:
                subprocess.Popen(cmd, start_new_session=True, env=clean_env)
        except Exception as e:
            logger.error("Failed executing launch subprocess for rom_id %s: %s", rom_id, e)

    def _uninstall_game(self, rom_id: int, file_path: str):
        """Delete ROM file or game directory from local storage and update SQLite database."""
        import shutil

        logger.info("Uninstalling ROM rom_id %s from local path: %s", rom_id, file_path)
        p_path = Path(file_path)
        download_dir = Path(self.settings.download_dir).resolve()

        # 1. Delete file or dedicated game directory from local filesystem
        try:
            p_resolved = p_path.resolve()
            parent_dir = p_resolved.parent
            # Check if parent_dir is a dedicated subfolder inside a platform directory (i.e. parent_dir.parent == download_dir/<platform>)
            if parent_dir.exists() and parent_dir.is_dir() and parent_dir.parent.resolve().parent == download_dir:
                shutil.rmtree(parent_dir)
                logger.info("Successfully deleted game directory at %s", parent_dir)
            elif p_resolved.exists():
                if p_resolved.is_file():
                    p_resolved.unlink()
                elif p_resolved.is_dir():
                    shutil.rmtree(p_resolved)
                logger.info("Successfully deleted ROM file at %s", p_resolved)
            else:
                logger.warning("ROM file at %s was already missing on disk.", file_path)
        except Exception as e:
            logger.error("Failed to delete ROM file/directory at %s: %s", file_path, e)
            return

        # 2. Remove record from SQLite db.installs
        try:
            with self.db_session as db:
                db.installs.delete(rom_id)
                db.commit()
            logger.info("Deleted RomInstall record for rom_id %s from SQLite database.", rom_id)
        except Exception as e:
            logger.error("Failed removing RomInstall record for rom_id %s from DB: %s", rom_id, e)

        # 3. Refresh Library view
        self.refresh()
