"""Main CustomTkinter GUI Desktop Application Window."""

import logging

import customtkinter as ctk

from romm_steam_sync.adapters.wrapper_installer import install_wrapper
from romm_steam_sync.config import AppSettings
from romm_steam_sync.logging_config import setup_logging
from romm_steam_sync.ui.views.cleanup_restore_view import CleanupRestoreView
from romm_steam_sync.ui.views.library_view import LibraryView
from romm_steam_sync.ui.views.onboarding_view import OnboardingView
from romm_steam_sync.ui.views.platform_select_view import PlatformSelectView
from romm_steam_sync.ui.views.settings_view import SettingsView
from romm_steam_sync.ui.views.sync_view import SyncView

logger = logging.getLogger(__name__)


class RommSteamSyncApp(ctk.CTk):
    """Main window for romm-steam-sync desktop application."""

    def __init__(self) -> None:
        """Initialize main application window, tab layout, and child views."""
        super().__init__()
        logger.info("Initializing RomM Steam Sync desktop GUI application...")

        # Appearance & Theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("RomM Steam Sync")
        self.geometry("960x700")
        self.minsize(860, 640)

        # Ensure launcher executable / wrapper is installed in config directory
        try:
            install_wrapper()
        except Exception as e:
            logger.warning(
                "Could not pre-install launcher wrapper on startup: %s", e
            )

        self.settings = AppSettings.load()

        # Main Layout Grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Tabview Container
        self.tabview = ctk.CTkTabview(
            self, corner_radius=10, command=self._on_tab_changed
        )
        self.tabview._segmented_button.configure(
            font=ctk.CTkFont(size=14, weight="bold")
        )

        # Add Navigation Tabs
        self.tab_library = self.tabview.add("Library")
        self.tab_platforms = self.tabview.add("Platform Selection")
        self.tab_sync = self.tabview.add("Library Sync")
        self.tab_cleanup = self.tabview.add("Cleanup & Restore")
        self.tab_settings = self.tabview.add("Settings")

        # Configure Tab Grid Layouts
        for tab in (
            self.tab_library,
            self.tab_platforms,
            self.tab_sync,
            self.tab_cleanup,
            self.tab_settings,
        ):
            tab.grid_rowconfigure(0, weight=1)
            tab.grid_columnconfigure(0, weight=1)

        # Initialize Tab Views
        self.library_view = LibraryView(
            self.tab_library,
            self.settings,
            on_navigate_tab=self._navigate_to_tab,
        )
        self.library_view.grid(row=0, column=0, sticky="nsew")

        self.platform_view = PlatformSelectView(
            self.tab_platforms, self.settings
        )
        self.platform_view.grid(row=0, column=0, sticky="nsew")

        self.sync_view = SyncView(self.tab_sync, self.settings)
        self.sync_view.grid(row=0, column=0, sticky="nsew")

        self.cleanup_view = CleanupRestoreView(self.tab_cleanup, self.settings)
        self.cleanup_view.grid(row=0, column=0, sticky="nsew")

        self.settings_view = SettingsView(
            self.tab_settings,
            self.settings,
            on_connect_success=self._on_server_connected,
        )
        self.settings_view.grid(row=0, column=0, sticky="nsew")

        # Check if onboarding wizard should be shown
        if not self.settings.onboarding_complete:
            logger.info("First run detected: displaying onboarding wizard.")
            self.onboarding_view = OnboardingView(
                self,
                self.settings,
                on_complete=self._on_onboarding_completed,
            )
            self.onboarding_view.grid(row=0, column=0, sticky="nsew")
        else:
            self.tabview.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
            self.tabview.set("Library")
            self.library_view.refresh()

    def _navigate_to_tab(self, tab_name: str) -> None:
        """Navigate to a specific tab and invoke tab change handler.

        Args:
            tab_name: Name of the tabview tab to select.
        """
        self.tabview.set(tab_name)
        self._on_tab_changed()

    def _on_onboarding_completed(self) -> None:
        """Handle completion of the onboarding wizard."""
        logger.info(
            "Onboarding wizard completed. Transitioning to main tab view."
        )
        if hasattr(self, "onboarding_view"):
            self.onboarding_view.grid_forget()
        self.tabview.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        self.tabview.set("Library")
        self.library_view.refresh()

    def _on_tab_changed(self) -> None:
        """Handle tab switching events."""
        current_tab = self.tabview.get()
        logger.debug("Switched navigation tab to: %s", current_tab)
        if current_tab == "Platform Selection":
            self.platform_view.ensure_populated()
        elif current_tab == "Library":
            self.library_view.refresh()

    def _on_server_connected(self) -> None:
        """Handle successful server connection from settings view."""
        logger.info(
            "RomM server connected successfully. Navigating to Platform Selection."
        )
        self.platform_view.load_platforms()
        self._navigate_to_tab("Platform Selection")


def main() -> None:
    """Main application entry point initializing logging and GUI loop."""
    setup_logging()
    logger.info("Starting RomM Steam Sync Desktop App...")
    try:
        app = RommSteamSyncApp()
        app.mainloop()
    except Exception as e:
        logger.critical(
            "Unhandled fatal exception in application GUI: %s",
            e,
            exc_info=True,
        )
        raise


if __name__ == "__main__":
    main()
