"""Platform checklist scrollable frame component."""

import logging
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.config import AppSettings

logger = logging.getLogger(__name__)


class PlatformChecklistFrame(ctk.CTkScrollableFrame):
    """Reusable scrollable frame displaying gaming platform checkboxes from RomM."""

    def __init__(
        self,
        parent: Any,
        label_text: str = "Available RomM Platforms",
        height: int = 320,
        **kwargs: Any,
    ) -> None:
        """Initialize PlatformChecklistFrame.

        Args:
            parent: Parent tkinter widget.
            label_text: Title label displayed at the top of scrollable frame.
            height: Frame height in pixels.
            **kwargs: Extra keyword arguments forwarded to CTkScrollableFrame.
        """
        super().__init__(
            parent,
            label_text=label_text,
            label_font=ctk.CTkFont(size=15, weight="bold"),
            height=height,
            **kwargs,
        )
        self.grid_columnconfigure(0, weight=1)
        self.checkbox_vars: Dict[str, ctk.BooleanVar] = {}

    def load_platforms(
        self,
        settings: AppSettings,
        client: Optional[RomMApiClient] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch platform entries from RomM server and populate checkboxes.

        Args:
            settings: Active AppSettings instance.
            client: Optional RomMApiClient instance; if omitted, initialized from settings.
            on_status: Optional callback receiving (status_message, color_hex).

        Returns:
            List of platform dictionaries fetched from RomM.
        """
        logger.info("Fetching available gaming platforms from RomM server...")
        if on_status:
            on_status("Fetching platforms from RomM server...", "#3498db")
        self.update_idletasks()

        for child in self.winfo_children():
            child.destroy()
        self.checkbox_vars.clear()

        api_client = client or RomMApiClient(
            base_url=settings.romm_url,
            api_key=settings.api_key,
        )

        try:
            platforms = api_client.get_platforms()
            if not platforms:
                logger.warning("No platforms returned from RomM server.")
                if on_status:
                    on_status("No platforms found on RomM server.", "#e67e22")
                return []

            enabled_set = set(settings.enabled_platforms)

            for idx, p in enumerate(platforms):
                slug = p.get("slug") or p.get("name", "").lower()
                name = p.get("name") or p.get("display_name") or slug
                rom_count = p.get("rom_count") or p.get("roms_count", 0)

                var = ctk.BooleanVar(value=(slug in enabled_set or not enabled_set))
                self.checkbox_vars[slug] = var

                lbl_text = f"{name} ({slug}) - {rom_count} games"
                cb = ctk.CTkCheckBox(
                    self,
                    text=lbl_text,
                    variable=var,
                    font=ctk.CTkFont(size=15),
                )
                cb.grid(row=idx, column=0, padx=15, pady=6, sticky="w")

            logger.info("Loaded %d platforms from RomM.", len(platforms))
            if on_status:
                on_status(f"Loaded {len(platforms)} platforms.", "#2ecc71")
            return platforms

        except Exception as e:
            logger.error("Failed to fetch platforms from RomM server: %s", e)
            if on_status:
                on_status(f"Failed to fetch platforms: {e}", "#e74c3c")
            return []

    def select_all(self) -> None:
        """Select all platform checkboxes in the checklist."""
        logger.info("Selecting all platforms in checklist (%d items).", len(self.checkbox_vars))
        for var in self.checkbox_vars.values():
            var.set(True)

    def deselect_all(self) -> None:
        """Deselect all platform checkboxes in the checklist."""
        logger.info("Deselecting all platforms in checklist (%d items).", len(self.checkbox_vars))
        for var in self.checkbox_vars.values():
            var.set(False)

    def get_selected_slugs(self) -> List[str]:
        """Return list of slugs corresponding to checked platform items.

        Returns:
            List of platform slug strings.
        """
        return [slug for slug, var in self.checkbox_vars.items() if var.get()]

    def save_selections(self, settings: AppSettings) -> List[str]:
        """Save selected platform slugs to application settings.

        Args:
            settings: Active AppSettings instance to persist selections into.

        Returns:
            List of selected platform slugs saved.
        """
        selected = self.get_selected_slugs()
        logger.info("Saving platform selection preferences: %s", selected)
        settings.enabled_platforms = selected
        settings.save()
        return selected
