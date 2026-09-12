"""ROM Cover Image Sliding Conveyor Component for Library Sync View."""

import logging
from pathlib import Path
import tkinter as tk
from typing import Any, Dict, List, Optional

import customtkinter as ctk
from PIL import Image

logger = logging.getLogger(__name__)

CARD_WIDTH = 110
CARD_HEIGHT = 170
CARD_SPACING = 15
TRACK_HEIGHT = 190
PADDING_LEFT = 15


class CoverTile(ctk.CTkFrame):
    """Card widget representing a single ROM shortcut cover art."""

    def __init__(
        self,
        parent: Any,
        rom_name: str,
        cover_path: Optional[str] = None,
    ) -> None:
        """Initialize CoverTile widget.

        Args:
            parent: Parent tkinter widget.
            rom_name: Display title of the ROM game.
            cover_path: Optional filesystem path to artwork image.
        """
        super().__init__(
            parent,
            width=CARD_WIDTH,
            height=CARD_HEIGHT,
            corner_radius=8,
            fg_color="#1e2533",
            border_width=1,
            border_color="#344158",
        )
        self.pack_propagate(False)
        self.grid_propagate(False)

        # Image Container Frame
        img_frame = ctk.CTkFrame(
            self,
            width=CARD_WIDTH - 8,
            height=135,
            fg_color="#141820",
            corner_radius=6,
        )
        img_frame.pack(padx=4, pady=(4, 2), fill="both", expand=True)
        img_frame.pack_propagate(False)

        loaded_image_label = False
        self._ctk_image: Optional[ctk.CTkImage] = None
        self._tk_image: Optional[tk.PhotoImage] = None

        if cover_path and Path(cover_path).exists():
            try:
                pil_img = Image.open(cover_path)
                pil_img.load()
                self._ctk_image = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(CARD_WIDTH - 12, 130),
                )
                lbl_img = ctk.CTkLabel(
                    img_frame,
                    image=self._ctk_image,
                    text="",
                )
                lbl_img.pack(fill="both", expand=True)
                loaded_image_label = True
            except (ImportError, ModuleNotFoundError) as e:
                logger.warning(
                    "Pillow Tkinter support (_imagingtk) unavailable for cover %s: %s. Falling back to native Tk PhotoImage.",
                    cover_path,
                    e,
                )
                try:
                    self._tk_image = tk.PhotoImage(file=cover_path)
                    lbl_img = tk.Label(
                        img_frame,
                        image=self._tk_image,
                        bg="#141820",
                        bd=0,
                    )
                    lbl_img.pack(fill="both", expand=True)
                    loaded_image_label = True
                except Exception as tk_err:
                    logger.debug(
                        "Native PhotoImage fallback failed for %s: %s",
                        cover_path,
                        tk_err,
                    )
            except Exception as e:
                logger.warning(
                    "Could not open/render cover image %s: %s",
                    cover_path,
                    e,
                )

        if not loaded_image_label:
            # Stylized Fallback Display
            fallback_label = ctk.CTkLabel(
                img_frame,
                text=(
                    rom_name[:12] + "..." if len(rom_name) > 14 else rom_name
                ),
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#95a5a6",
            )
            fallback_label.pack(expand=True)

        # Game Title Label
        truncated_name = (
            rom_name if len(rom_name) <= 16 else rom_name[:14] + "..."
        )
        name_lbl = ctk.CTkLabel(
            self,
            text=truncated_name,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ecf0f1",
        )
        name_lbl.pack(padx=4, pady=(2, 4), side="bottom")


class RomCoverConveyor(ctk.CTkFrame):
    """Horizontal track container displaying animated ROM cover images sliding left to right."""

    def __init__(self, parent: Any) -> None:
        """Initialize RomCoverConveyor track container.

        Args:
            parent: Parent tkinter widget.
        """
        super().__init__(parent, fg_color="transparent")

        self.cards: List[Dict[str, Any]] = []
        self.shortcut_count = 0
        self._animating = False

        self.grid_columnconfigure(0, weight=1)

        # Header Bar
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        header_frame.grid_columnconfigure(1, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Synced Steam Shortcuts",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        title_lbl.grid(row=0, column=0, sticky="w")

        self.count_badge = ctk.CTkLabel(
            header_frame,
            text="0 created",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#3498db",
            fg_color="#1c2833",
            corner_radius=6,
            padx=8,
            pady=2,
        )
        self.count_badge.grid(row=0, column=1, sticky="w", padx=10)

        # Log Drawer Toggle Button
        self.log_toggle_btn = ctk.CTkButton(
            header_frame,
            text="Show Logs",
            command=self.toggle_logs,
            font=ctk.CTkFont(size=12),
            width=100,
            height=26,
            fg_color="#2c3e50",
            hover_color="#34495e",
        )
        self.log_toggle_btn.grid(row=0, column=2, sticky="e")

        # Track Viewport Frame (Horizontal Conveyor Container)
        self.track_frame = ctk.CTkFrame(
            self,
            height=TRACK_HEIGHT,
            fg_color="#12161f",
            corner_radius=10,
            border_width=1,
            border_color="#242c3d",
        )
        self.track_frame.grid(row=1, column=0, sticky="ew")
        self.track_frame.pack_propagate(False)
        self.track_frame.grid_propagate(False)

        # Placeholder Overlay Label when empty
        self.placeholder_lbl = ctk.CTkLabel(
            self.track_frame,
            text="Ready to sync!",
            font=ctk.CTkFont(size=14, weight="normal"),
            text_color="#7f8c8d",
        )
        self.placeholder_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Optional Collapsible Log Drawer Textbox
        self.logs_visible = False
        self.log_drawer = ctk.CTkTextbox(
            self,
            height=90,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="#0e1117",
        )

    def add_cover(
        self, rom_name: str, cover_path: Optional[str] = None
    ) -> None:
        """Add a newly created ROM cover to the conveyor, sliding it in from left to right.

        Args:
            rom_name: Title of the ROM game.
            cover_path: Optional path to artwork image file.
        """
        if self.placeholder_lbl.winfo_viewable():
            self.placeholder_lbl.place_forget()

        self.shortcut_count += 1
        self.count_badge.configure(text=f"{self.shortcut_count} created")

        # 1. Shift all existing cards right by (CARD_WIDTH + CARD_SPACING)
        shift_amount = CARD_WIDTH + CARD_SPACING
        for card_info in self.cards:
            card_info["target_x"] += shift_amount

        # 2. Create new CoverTile widget starting off-screen on the left
        start_x = -CARD_WIDTH - 20
        target_x = PADDING_LEFT

        widget = CoverTile(
            self.track_frame, rom_name=rom_name, cover_path=cover_path
        )
        widget.place(x=start_x, y=14)

        self.cards.insert(
            0,
            {
                "widget": widget,
                "current_x": float(start_x),
                "target_x": float(target_x),
                "rom_name": rom_name,
            },
        )

        # 3. Trigger smooth animation loop
        if not self._animating:
            self._animating = True
            self.after(16, self._animate_frame)

    def _animate_frame(self) -> None:
        """Interpolate current_x towards target_x for all cards (~60 FPS)."""
        still_moving = False
        tw = self.track_frame.winfo_width()
        track_width = tw if tw > 1 else 800

        to_remove = []

        for card_info in self.cards:
            curr = card_info["current_x"]
            target = card_info["target_x"]

            diff = target - curr
            if abs(diff) > 0.5:
                step = diff * 0.28  # Smooth ease-out multiplier
                new_x = curr + step
                card_info["current_x"] = new_x
                card_info["widget"].place(x=int(new_x), y=14)
                still_moving = True
            else:
                card_info["current_x"] = target
                card_info["widget"].place(x=int(target), y=14)

            # Cleanup cards pushed beyond track's right edge
            if card_info["current_x"] > track_width + 40:
                to_remove.append(card_info)

        for card_info in to_remove:
            card_info["widget"].destroy()
            if card_info in self.cards:
                self.cards.remove(card_info)

        if still_moving:
            self.after(16, self._animate_frame)
        else:
            self._animating = False

    def clear(self) -> None:
        """Reset the conveyor track state."""
        for card_info in self.cards:
            card_info["widget"].destroy()
        self.cards.clear()
        self.shortcut_count = 0
        self.count_badge.configure(text="0 created")
        self.placeholder_lbl.place(relx=0.5, rely=0.5, anchor="center")
        self.log_drawer.delete("1.0", "end")

    def append_log(self, text: str) -> None:
        """Append log message to the collapsible log drawer.

        Args:
            text: Log message string.
        """
        self.log_drawer.insert("end", text + "\n")
        self.log_drawer.see("end")

    def toggle_logs(self) -> None:
        """Toggle collapsible log drawer visibility."""
        if self.logs_visible:
            self.log_drawer.grid_forget()
            if hasattr(self, "grid_rowconfigure"):
                try:
                    self.grid_rowconfigure(2, weight=0)
                    self.grid_rowconfigure(1, weight=1)
                except Exception as e:
                    logger.debug("Could not reset conveyor row weights: %s", e)
            self.log_toggle_btn.configure(text="Show Logs")
            self.logs_visible = False
        else:
            if hasattr(self, "grid_rowconfigure"):
                try:
                    self.grid_rowconfigure(1, weight=0)
                    self.grid_rowconfigure(2, weight=1)
                except Exception as e:
                    logger.debug("Could not set conveyor row weights: %s", e)
            self.log_drawer.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
            self.log_toggle_btn.configure(text="Hide Logs")
            self.logs_visible = True
