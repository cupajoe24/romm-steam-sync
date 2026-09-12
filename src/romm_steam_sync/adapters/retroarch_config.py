"""RetroArch configuration parser and save directory resolver.

Reads retroarch.cfg runtime settings and libretro core .info metadata to accurately
determine where RetroArch reads and writes save files across Steam, Standalone, and RetroDECK.
"""

import logging
from pathlib import Path
import sys
from typing import Any, Dict, Optional

from romm_steam_sync.adapters.retroarch.base import (
    CORE_NAME_FALLBACKS,
    parse_core_info,
    parse_retroarch_cfg_line,
)
from romm_steam_sync.adapters.retroarch.detector import get_retroarch_adapter
from romm_steam_sync.adapters.retroarch_launcher import RetroArchLauncher
from romm_steam_sync.adapters.retroarch_paths import RetroArchPathResolver

logger = logging.getLogger(__name__)

__all__ = [
    "CORE_NAME_FALLBACKS",
    "parse_core_info",
    "parse_retroarch_cfg_line",
    "RetroArchConfigAdapter",
    "RetroArchLauncher",
]


class RetroArchConfigAdapter:
    """Adapter to inspect RetroArch runtime configuration and resolve save paths."""

    def __init__(self, configured_retroarch_path: str = "") -> None:
        """Initialize adapter.

        Args:
            configured_retroarch_path: Optional user-configured path to RetroArch binary or directory.
        """
        self.configured_retroarch_path = configured_retroarch_path
        self._cfg_path: Optional[Path] = None
        self._cached_settings: Optional[Dict[str, Any]] = None
        self._adapter = get_retroarch_adapter(configured_retroarch_path)

    def resolve_retroarch_cfg_path(self) -> Optional[Path]:
        """Locate retroarch.cfg file across configured and standard platform paths.

        Returns:
            Resolved Path to retroarch.cfg or None if not located.
        """
        if self._cfg_path is not None and self._cfg_path.is_file():
            return self._cfg_path

        cfg = self._adapter.resolve_cfg_path()
        if cfg:
            self._cfg_path = cfg
            return self._cfg_path

        # Also fallback to RetroArchPathResolver if patched in unit tests
        cfg_fallback = RetroArchPathResolver.resolve_retroarch_cfg_path(
            configured_path=self.configured_retroarch_path,
            os_platform=sys.platform,
            home_dir=Path.home(),
        )
        if cfg_fallback:
            self._cfg_path = cfg_fallback
            return self._cfg_path

        return None

    def get_config_settings(self) -> Dict[str, Any]:
        """Read and parse runtime save settings from retroarch.cfg.

        Returns:
            Dictionary with parsed settings:
            - savefiles_in_content_dir: bool
            - savefile_directory: str
            - sort_savefiles_by_content_enable: bool
            - sort_savefiles_enable: bool
            - libretro_info_path: str
        """
        if self._cached_settings is not None:
            return self._cached_settings

        self._cached_settings = self._adapter.get_config_settings()
        return self._cached_settings

    def resolve_saves_base_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve absolute base directory for RetroArch save files.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to the saves root directory.
        """
        return self._adapter.resolve_saves_base_dir(settings=settings)

    def resolve_core_name(
        self,
        core_identifier: str,
        platform_slug: str = "",
        settings: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Determine canonical RetroArch core name for directory sorting.

        Args:
            core_identifier: Libretro core identifier (e.g. 'mgba_libretro').
            platform_slug: Optional platform slug identifier.
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Canonical core name string (e.g. 'mGBA') or normalized identifier.
        """
        return self._adapter.resolve_core_name(
            core_identifier=core_identifier,
            platform_slug=platform_slug,
            settings=settings,
        )

    def resolve_save_directory(
        self,
        rom_path: str,
        platform_slug: str = "",
        core_name: str = "",
    ) -> Path:
        """Resolve the target directory where RetroArch expects save files to live.

        Respects savefiles_in_content_dir, sort_savefiles_by_content_enable,
        and sort_savefiles_enable across detected flavor defaults.

        Args:
            rom_path: Path to the target ROM file.
            platform_slug: Optional platform slug identifier.
            core_name: Optional libretro core identifier.

        Returns:
            Resolved absolute Path to directory where saves should be placed.
        """
        cfg_p = self.resolve_retroarch_cfg_path()
        ra_exe = RetroArchLauncher.resolve_retroarch_binary(
            self.configured_retroarch_path
        )
        rom_p = Path(rom_path)

        # If RetroArch is not installed and no cfg is located, fallback to ROM directory
        if not cfg_p and not ra_exe:
            return rom_p.parent.resolve()

        return self._adapter.resolve_save_directory(
            rom_path=rom_path,
            platform_slug=platform_slug,
            core_name=core_name,
        )
