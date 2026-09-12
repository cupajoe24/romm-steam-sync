"""Game Detail & Actions Modal for Installed ROMs in Library View."""

from datetime import datetime
import logging
import os
from pathlib import Path
import tkinter as tk
from typing import Any, Callable, Optional

import customtkinter as ctk
from PIL import Image

logger = logging.getLogger(__name__)


def format_size(size_bytes: int) -> str:
    """Format byte count into human-readable size string.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Formatted string (e.g., '12.5 MB').
    """
    if size_bytes <= 0:
        return "Unknown size"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class GameDetailModal(ctk.CTkToplevel):
    """Modal dialog displaying installed ROM details with Launch and Uninstall options."""

    def __init__(
        self,
        parent: Any,
        rom_id: int,
        rom_name: str,
        platform_slug: str,
        file_path: str,
        cover_path: Optional[str] = None,
        on_launch: Optional[Callable[[int, str], None]] = None,
        on_uninstall: Optional[Callable[[int, str], None]] = None,
    ) -> None:
        """Initialize GameDetailModal dialog.

        Args:
            parent: Parent tkinter widget.
            rom_id: RomM identifier of the game.
            rom_name: Display title of the game.
            platform_slug: Platform identifier slug.
            file_path: Path to the local ROM file.
            cover_path: Optional path to artwork image.
            on_launch: Optional callback to execute when user clicks Launch.
            on_uninstall: Optional callback to execute when user confirms Uninstall.
        """
        super().__init__(parent)
        self.rom_id = rom_id
        self.rom_name = rom_name
        self.platform_slug = (
            platform_slug.lower() if platform_slug else "unknown"
        )
        self.file_path = file_path
        self.cover_path = cover_path
        self.on_launch = on_launch
        self.on_uninstall = on_uninstall

        logger.info(
            "Opening GameDetailModal for rom_id %s (%s)",
            self.rom_id,
            self.rom_name,
        )

        self.title(f"{self.rom_name} - RomM Library")
        self.geometry("600x460")
        self.minsize(580, 420)
        self.resizable(True, True)
        self.attributes("-topmost", True)

        # Associate with toplevel window if available
        try:
            top_level = (
                parent.winfo_toplevel()
                if hasattr(parent, "winfo_toplevel")
                else parent
            )
            if top_level and top_level != self:
                self.transient(top_level)
        except Exception as e:
            logger.debug("Could not set transient master for modal: %s", e)

        self.confirm_uninstall_mode = False
        try:
            self._build_ui()
        except Exception as e:
            logger.error(
                "Error building GameDetailModal UI for rom_id %s: %s",
                self.rom_id,
                e,
                exc_info=True,
            )

        # Center modal relative to parent window AFTER building UI
        try:
            self.update_idletasks()
            top_level = (
                parent.winfo_toplevel()
                if hasattr(parent, "winfo_toplevel")
                else parent
            )
            pw = top_level.winfo_width() if top_level else 800
            ph = top_level.winfo_height() if top_level else 600
            px = top_level.winfo_rootx() if top_level else 100
            py = top_level.winfo_rooty() if top_level else 100
            dw = 600
            dh = 460
            x = px + max(0, (pw - dw) // 2)
            y = py + max(0, (ph - dh) // 2)
            self.geometry(f"{dw}x{dh}+{x}+{y}")
        except Exception as e:
            logger.debug("Could not center modal on parent: %s", e)

        self.after(50, self.lift)
        self.after(50, self.focus_force)

    def _build_ui(self) -> None:
        """Construct inner grid layouts and information widgets."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header Frame
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text=self.rom_name,
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        platform_badge = ctk.CTkLabel(
            header_frame,
            text=self.platform_slug.upper(),
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2c3e50",
            text_color="#ecf0f1",
            corner_radius=6,
            padx=10,
            pady=4,
        )
        platform_badge.grid(row=0, column=1, sticky="e")

        # Body Content Frame (Cover on left, details on right)
        body_frame = ctk.CTkFrame(self, fg_color="transparent")
        body_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        body_frame.grid_columnconfigure(1, weight=1)
        body_frame.grid_rowconfigure(0, weight=1)

        # Left Column: Cover Art
        cover_frame = ctk.CTkFrame(
            body_frame,
            width=150,
            height=225,
            fg_color="#12161f",
            corner_radius=8,
            border_width=1,
            border_color="#242c3d",
        )
        cover_frame.grid(row=0, column=0, padx=(0, 20), sticky="nw")
        cover_frame.pack_propagate(False)
        cover_frame.grid_propagate(False)

        loaded_cover_label = False
        self._ctk_cover: Optional[ctk.CTkImage] = None
        self._tk_cover: Optional[tk.PhotoImage] = None

        if self.cover_path and Path(self.cover_path).exists():
            try:
                pil_img = Image.open(self.cover_path)
                pil_img.load()
                self._ctk_cover = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(140, 215),
                )
                cover_lbl = ctk.CTkLabel(
                    cover_frame, image=self._ctk_cover, text=""
                )
                cover_lbl.pack(fill="both", expand=True)
                loaded_cover_label = True
            except (ImportError, ModuleNotFoundError) as e:
                logger.warning(
                    "Pillow Tkinter support (_imagingtk) unavailable for modal cover %s: %s. Falling back to native Tk PhotoImage.",
                    self.cover_path,
                    e,
                )
                try:
                    self._tk_cover = tk.PhotoImage(file=self.cover_path)
                    cover_lbl = tk.Label(
                        cover_frame,
                        image=self._tk_cover,
                        bg="#12161f",
                        bd=0,
                    )
                    cover_lbl.pack(fill="both", expand=True)
                    loaded_cover_label = True
                except Exception as tk_err:
                    logger.debug(
                        "Native PhotoImage fallback failed for %s: %s",
                        self.cover_path,
                        tk_err,
                    )
            except Exception as e:
                logger.warning(
                    "Could not open/render cover image %s: %s",
                    self.cover_path,
                    e,
                )

        if not loaded_cover_label:
            fallback_lbl = ctk.CTkLabel(
                cover_frame,
                text="No Cover Art",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#7f8c8d",
            )
            fallback_lbl.pack(expand=True)

        # Right Column: Details Info Card
        details_frame = ctk.CTkFrame(
            body_frame,
            fg_color="#1a202c",
            corner_radius=8,
            border_width=1,
            border_color="#2d3748",
        )
        details_frame.grid(row=0, column=1, sticky="nsew")
        details_frame.grid_columnconfigure(1, weight=1)

        # Retrieve file metadata
        file_size_str = "Unknown"
        mtime_str = "Unknown"
        rom_p = Path(self.file_path)
        if rom_p.exists():
            try:
                st = rom_p.stat()
                file_size_str = format_size(st.st_size)
                mtime_str = datetime.fromtimestamp(st.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except Exception as e:
                logger.debug("Error reading file stat for %s: %s", rom_p, e)

        meta_rows = [
            ("ROM ID:", str(self.rom_id)),
            ("Platform:", self.platform_slug.title()),
            ("File Size:", file_size_str),
            ("Modified:", mtime_str),
            ("File Path:", str(self.file_path)),
        ]

        for i, (label, val) in enumerate(meta_rows):
            key_lbl = ctk.CTkLabel(
                details_frame,
                text=label,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#a0aec0",
                anchor="w",
            )
            key_lbl.grid(row=i, column=0, padx=(15, 10), pady=(12 if i == 0 else 6, 6), sticky="nw")

            val_lbl = ctk.CTkLabel(
                details_frame,
                text=val,
                font=ctk.CTkFont(size=13),
                text_color="#edf2f7",
                anchor="w",
                wraplength=260,
                justify="left",
            )
            val_lbl.grid(row=i, column=1, sticky="nw", pady=(12 if i == 0 else 6, 6))

        # Bottom Action Bar
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.grid(
            row=2, column=0, padx=20, pady=(5, 20), sticky="ew"
        )
        self.action_frame.grid_columnconfigure(1, weight=1)

        self._render_normal_action_buttons()

    def _render_normal_action_buttons(self) -> None:
        """Render standard Launch and Uninstall buttons."""
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        self.uninstall_btn = ctk.CTkButton(
            self.action_frame,
            text="Uninstall ROM",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#c53030",
            hover_color="#9b2c2c",
            width=140,
            height=36,
            command=self._prompt_uninstall_confirm,
        )
        self.uninstall_btn.pack(side="left", padx=(0, 10))

        self.cancel_btn = ctk.CTkButton(
            self.action_frame,
            text="Close",
            font=ctk.CTkFont(size=13),
            fg_color="#4a5568",
            hover_color="#2d3748",
            width=90,
            height=36,
            command=self.destroy,
        )
        self.cancel_btn.pack(side="right", padx=(10, 0))

        self.launch_btn = ctk.CTkButton(
            self.action_frame,
            text="Launch Game",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2b6cb0",
            hover_color="#2c5282",
            width=150,
            height=36,
            command=self._handle_launch,
        )
        self.launch_btn.pack(side="right")

    def _prompt_uninstall_confirm(self) -> None:
        """Show confirmation prompt before deleting ROM file."""
        for widget in self.action_frame.winfo_children():
            widget.destroy()

        confirm_lbl = ctk.CTkLabel(
            self.action_frame,
            text="Really delete ROM file from local storage?",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#fc8181",
        )
        confirm_lbl.pack(side="left", padx=(0, 10))

        cancel_confirm_btn = ctk.CTkButton(
            self.action_frame,
            text="Cancel",
            font=ctk.CTkFont(size=12),
            fg_color="#4a5568",
            hover_color="#2d3748",
            width=80,
            height=34,
            command=self._render_normal_action_buttons,
        )
        cancel_confirm_btn.pack(side="right", padx=(10, 0))

        execute_uninstall_btn = ctk.CTkButton(
            self.action_frame,
            text="Confirm Uninstall",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#e53e3e",
            hover_color="#c53030",
            width=140,
            height=34,
            command=self._handle_uninstall,
        )
        execute_uninstall_btn.pack(side="right")

    def _handle_launch(self) -> None:
        """Invoke launch callback and close modal."""
        logger.info(
            "Launch triggered for rom_id %s (%s)", self.rom_id, self.rom_name
        )
        if self.on_launch:
            try:
                self.on_launch(self.rom_id, self.platform_slug)
            except Exception as e:
                logger.error(
                    "Error executing launch callback for rom_id %s: %s",
                    self.rom_id,
                    e,
                )
        self.destroy()

    def _handle_uninstall(self) -> None:
        """Invoke uninstall callback and close modal."""
        logger.info(
            "Uninstall confirmed for rom_id %s (%s) at %s",
            self.rom_id,
            self.rom_name,
            self.file_path,
        )
        if self.on_uninstall:
            try:
                self.on_uninstall(self.rom_id, self.file_path)
            except Exception as e:
                logger.error(
                    "Error executing uninstall callback for rom_id %s: %s",
                    self.rom_id,
                    e,
                )
        self.destroy()
