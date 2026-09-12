"""Application settings and JSON persistence configuration."""

from dataclasses import asdict, dataclass, field
import json
import logging
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional
import uuid

from romm_steam_sync.domain.platform import (
    lookup_platform_mapping,
    normalize_platform_slug,
)

logger = logging.getLogger(__name__)


def get_default_config_dir() -> Path:
    """Get the cross-platform user configuration directory for romm-steam-sync.

    Returns:
        Path to the configuration directory, guaranteed to exist.
    """
    if os.name == "nt":
        app_data = os.environ.get("APPDATA")
        if app_data:
            base = Path(app_data)
        else:
            base = Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    config_dir = base / "romm-steam-sync"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@dataclass
class AppSettings:
    """Application-wide settings persisted to settings.json.

    Attributes:
        romm_url: Base URL of the RomM server instance.
        api_key: API key for RomM authentication.
        steamgriddb_api_key: Optional API key for SteamGridDB artwork fetching.
        steam_user_id: Target Steam account user ID, or 'auto' for automatic detection.
        steam_custom_path: Optional custom Steam installation directory.
        enabled_platforms: List of platform slugs enabled for synchronization.
        download_dir: Local directory for on-demand ROM downloads.
        retroarch_path: Custom executable path to RetroArch.
        emulator_flavor: Selected emulator distribution flavor ('auto', 'steam', 'standalone', 'retrodeck').
        core_mappings: Mapping of platform slug to preferred libretro core.
        default_slot: Default save slot identifier (e.g. 'autosave', 'slot1').
        save_sync_enabled: Whether save file synchronization with RomM is enabled.
        onboarding_complete: Whether initial onboarding wizard was completed.
        device_id: Unique UUID identifier for this client installation.
    """

    romm_url: str = "http://"
    api_key: str = ""
    steamgriddb_api_key: str = ""
    steam_user_id: str = "auto"
    steam_custom_path: str = ""
    enabled_platforms: List[str] = field(default_factory=list)
    download_dir: str = field(
        default_factory=lambda: str(get_default_config_dir() / "roms")
    )
    retroarch_path: str = ""
    emulator_flavor: str = "auto"
    core_mappings: Dict[str, str] = field(default_factory=dict)
    default_slot: str = "autosave"
    save_sync_enabled: bool = True
    onboarding_complete: bool = False
    device_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def get_settings_file(cls) -> Path:
        """Get the filesystem path to settings.json.

        Returns:
            Path object pointing to settings.json.
        """
        return get_default_config_dir() / "settings.json"

    @classmethod
    def load(cls) -> "AppSettings":
        """Load settings from disk, creating default settings if missing.

        Returns:
            Loaded or newly created AppSettings instance.
        """
        path = cls.get_settings_file()
        if not path.exists():
            settings = cls()
            settings.save()
            return settings
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            settings = cls(
                **{k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            )
            if not settings.device_id:
                settings.device_id = str(uuid.uuid4())
                settings.save()
            return settings
        except Exception as e:
            logger.warning(
                "Failed to load settings from %s, falling back to defaults: %s",
                path,
                e,
            )
            return cls()

    def save(self) -> None:
        """Persist current settings to settings.json."""
        path = self.get_settings_file()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
            logger.debug("Successfully saved settings to %s", path)
        except Exception as e:
            logger.error("Failed to save settings to %s: %s", path, e)

    def get_core_override(self, platform_slug: str) -> Optional[str]:
        """Get custom libretro core override for a platform slug if set.

        Args:
            platform_slug: Platform identifier slug.

        Returns:
            Configured core override name, or None if using default.
        """
        if not platform_slug or not self.core_mappings:
            return None
        return lookup_platform_mapping(self.core_mappings, platform_slug)

    def set_core_override(self, platform_slug: str, core_name: str) -> None:
        """Set or update a custom libretro core override for a platform slug.

        Args:
            platform_slug: Platform identifier slug.
            core_name: Libretro core name to associate.
        """
        if not platform_slug:
            return
        slug_key = platform_slug.lower().strip()
        clean_core = core_name.strip()
        if not clean_core:
            self.remove_core_override(slug_key)
            return
        if self.core_mappings is None:
            self.core_mappings = {}
        self.core_mappings[slug_key] = clean_core

    def remove_core_override(self, platform_slug: str) -> None:
        """Remove a custom core override, reverting the platform to its default core.

        Args:
            platform_slug: Platform identifier slug.
        """
        if not platform_slug or not self.core_mappings:
            return
        for k in normalize_platform_slug(platform_slug):
            if k:
                self.core_mappings.pop(k, None)

    def clear_all_core_overrides(self) -> None:
        """Clear all custom core mappings, restoring defaults across all platforms."""
        self.core_mappings = {}
