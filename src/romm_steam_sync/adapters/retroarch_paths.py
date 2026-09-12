"""RetroArch path resolution, core naming conventions, and filesystem discovery.

Provides centralized platform-aware discovery for RetroArch executable binaries,
configuration files (retroarch.cfg), libretro core libraries, .info metadata,
and save file directories across Steam, Standalone, and RetroDECK environments.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from romm_steam_sync.adapters.retroarch.base import (
    ensure_core_suffix,
    get_core_suffix,
    lookup_platform_mapping,
    normalize_core_stem,
    normalize_platform_slug,
    strip_core_suffix,
)
from romm_steam_sync.adapters.retroarch.detector import detect_retroarch_flavor
from romm_steam_sync.adapters.retroarch.steam import SteamRetroArchAdapter

logger = logging.getLogger(__name__)

__all__ = [
    "normalize_platform_slug",
    "lookup_platform_mapping",
    "get_core_suffix",
    "strip_core_suffix",
    "ensure_core_suffix",
    "normalize_core_stem",
    "RetroArchPathResolver",
]


class RetroArchPathResolver:
    """Centralized facade for RetroArch filesystem paths across flavors and platforms."""

    @classmethod
    def resolve_retroarch_binary(
        cls,
        configured_path: str = "",
        os_platform: Optional[str] = None,
        home_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Locate RetroArch executable binary across detected flavors.

        Args:
            configured_path: User-configured path to RetroArch binary or folder.
            os_platform: Optional OS identifier ('win32', 'darwin', 'linux').
            home_dir: Optional user home directory Path.

        Returns:
            Resolved absolute Path to RetroArch binary or None if not found.
        """
        adapter = detect_retroarch_flavor(
            configured_path=configured_path,
            os_platform=os_platform,
            home_dir=home_dir,
        )
        return adapter.resolve_binary()

    @classmethod
    def resolve_retroarch_cfg_path(
        cls,
        configured_path: str = "",
        os_platform: Optional[str] = None,
        home_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """Locate retroarch.cfg file across configured and standard platform paths.

        Args:
            configured_path: User-configured path to RetroArch binary or folder.
            os_platform: Optional OS identifier ('win32', 'darwin', 'linux').
            home_dir: Optional user home directory Path.

        Returns:
            Resolved absolute Path to retroarch.cfg or None if not found.
        """
        adapter = detect_retroarch_flavor(
            configured_path=configured_path,
            os_platform=os_platform,
            home_dir=home_dir,
        )
        return adapter.resolve_cfg_path()

    @classmethod
    def get_core_search_dirs(
        cls,
        retroarch_path: str = "",
        os_platform: Optional[str] = None,
        home_dir: Optional[Path] = None,
    ) -> List[Path]:
        """Collect directories to search for libretro core libraries.

        Args:
            retroarch_path: Optional path to configured RetroArch binary or folder.
            os_platform: Optional OS identifier ('win32', 'darwin', 'linux').
            home_dir: Optional user home directory Path.

        Returns:
            List of directory Path objects in priority search order.
        """
        adapter = detect_retroarch_flavor(
            configured_path=retroarch_path,
            os_platform=os_platform,
            home_dir=home_dir,
        )
        return adapter.get_core_search_dirs()

    @classmethod
    def get_info_search_dirs(
        cls,
        retroarch_path: str = "",
        raw_info_path: str = "",
        os_platform: Optional[str] = None,
        home_dir: Optional[Path] = None,
    ) -> List[Path]:
        """Collect directories to search for libretro core .info metadata files.

        Args:
            retroarch_path: Optional path to configured RetroArch binary or folder.
            raw_info_path: Optional raw 'libretro_info_path' setting from retroarch.cfg.
            os_platform: Optional OS identifier ('win32', 'darwin', 'linux').
            home_dir: Optional user home directory Path.

        Returns:
            List of directory Path objects in priority search order.
        """
        adapter = detect_retroarch_flavor(
            configured_path=retroarch_path,
            os_platform=os_platform,
            home_dir=home_dir,
        )
        return adapter.get_info_search_dirs(raw_info_path=raw_info_path)

    @classmethod
    def resolve_saves_base_dir(
        cls,
        configured_path: str = "",
        savefile_directory: str = "",
        os_platform: Optional[str] = None,
        home_dir: Optional[Path] = None,
    ) -> Path:
        """Resolve absolute base directory for RetroArch save files.

        Args:
            configured_path: Optional path to configured RetroArch binary or folder.
            savefile_directory: Raw 'savefile_directory' value from retroarch.cfg.
            os_platform: Optional OS identifier ('win32', 'darwin', 'linux').
            home_dir: Optional user home directory Path.

        Returns:
            Resolved absolute Path to the saves root directory.
        """
        resolved_exe = cls.resolve_retroarch_binary(
            configured_path=configured_path,
            os_platform=os_platform,
            home_dir=home_dir,
        )
        if not resolved_exe and not configured_path:
            from romm_steam_sync.adapters.retroarch.standalone import StandaloneRetroArchAdapter

            adapter = StandaloneRetroArchAdapter(
                configured_path="",
                os_platform=os_platform,
                home_dir=home_dir,
            )
        else:
            adapter = detect_retroarch_flavor(
                configured_path=str(resolved_exe) if resolved_exe else configured_path,
                os_platform=os_platform,
                home_dir=home_dir,
            )
        settings = (
            {"savefile_directory": savefile_directory}
            if savefile_directory
            else None
        )
        return adapter.resolve_saves_base_dir(settings=settings)

    @classmethod
    def resolve_steam_linux_runtime(
        cls,
        retroarch_path: str = "",
        os_platform: Optional[str] = None,
    ) -> Optional[Path]:
        """Locate Steam Linux Runtime runner script for Steam RetroArch on Linux.

        Args:
            retroarch_path: Optional path to RetroArch binary or directory.
            os_platform: Optional OS identifier ('win32', 'darwin', 'linux').

        Returns:
            Path to runtime runner script or executable, or None if not located.
        """
        adapter = SteamRetroArchAdapter(
            configured_path=retroarch_path, os_platform=os_platform
        )
        return adapter.resolve_steam_linux_runtime()
