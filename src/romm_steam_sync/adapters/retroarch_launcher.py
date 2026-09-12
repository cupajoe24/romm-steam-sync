"""RetroArch process execution adapter and core resolution facade."""

import logging
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from romm_steam_sync.adapters.retroarch.base import (
    DEFAULT_CORE_MAPPINGS,
    PLATFORM_CORE_CANDIDATES,
    bring_process_window_to_foreground,
    clean_subprocess_env,
    get_core_suffix as _get_core_suffix,
    is_retroarch_running,
    lookup_platform_mapping,
    strip_core_suffix,
)
from romm_steam_sync.adapters.retroarch.detector import get_retroarch_adapter
from romm_steam_sync.adapters.retroarch.steam import SteamRetroArchAdapter

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_CORE_MAPPINGS",
    "PLATFORM_CORE_CANDIDATES",
    "get_default_core_for_platform",
    "get_core_candidates_for_platform",
    "list_installed_cores",
    "get_core_suffix",
    "bring_process_window_to_foreground",
    "clean_subprocess_env",
    "is_retroarch_running",
    "RetroArchLauncher",
]


def get_default_core_for_platform(platform_slug: str) -> Optional[str]:
    """Get the standard default libretro core for a platform slug.

    Args:
        platform_slug: Platform identifier slug.

    Returns:
        Default libretro core name, or None if unknown.
    """
    if not platform_slug:
        return None
    return lookup_platform_mapping(DEFAULT_CORE_MAPPINGS, platform_slug)


def get_core_candidates_for_platform(platform_slug: str) -> List[str]:
    """Get candidate libretro cores for a given platform slug.

    Args:
        platform_slug: Platform identifier slug.

    Returns:
        List of candidate libretro core names.
    """
    if not platform_slug:
        return []
    candidates = (
        lookup_platform_mapping(PLATFORM_CORE_CANDIDATES, platform_slug) or []
    )
    res = list(candidates)
    default_core = get_default_core_for_platform(platform_slug)
    if default_core and default_core not in res:
        res.insert(0, default_core)
    return res


def get_core_suffix() -> str:
    """Get dynamic libretro core file extension for the current OS.

    Returns:
        '.dll' on Windows, '.dylib' on macOS, or '.so' on Linux.
    """
    return _get_core_suffix(os_platform=sys.platform)


def list_installed_cores(retroarch_path: str = "") -> List[str]:
    """Scan search directories for physically installed libretro cores.

    Args:
        retroarch_path: Optional path to configured RetroArch binary or directory.

    Returns:
        Sorted list of discovered bare core names (without OS suffix).
    """
    adapter = get_retroarch_adapter(configured_path=retroarch_path)
    return adapter.list_installed_cores()


class RetroArchLauncher:
    """Helper to locate RetroArch executable, resolve libretro cores, and spawn retroarch processes."""

    @staticmethod
    def resolve_retroarch_binary(configured_path: str = "") -> Optional[str]:
        """Locate RetroArch executable binary across detected flavors.

        Args:
            configured_path: User-configured path to RetroArch executable or folder.

        Returns:
            Resolved absolute path to RetroArch binary or None if not found.
        """
        adapter = get_retroarch_adapter(configured_path=configured_path)
        resolved = adapter.resolve_binary()
        if not resolved:
            return None
        posix = resolved.as_posix()
        if posix.startswith("/"):
            return posix
        return str(resolved)

    @staticmethod
    def resolve_core_path(
        platform_slug: str,
        retroarch_exe: str = "",
        custom_mappings: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Locate libretro core file path for a given platform slug.

        Args:
            platform_slug: Platform identifier slug.
            retroarch_exe: Path to the RetroArch binary.
            custom_mappings: Optional user core mappings dict.

        Returns:
            Resolved core path or core filename string.
        """
        adapter = get_retroarch_adapter(configured_path=retroarch_exe)
        return adapter.resolve_core_path(
            platform_slug=platform_slug, custom_mappings=custom_mappings
        )

    @classmethod
    def resolve_steam_linux_runtime(
        cls,
        retroarch_path: str = "",
    ) -> Optional[Path]:
        """Locate Steam Linux Runtime runner script for Steam RetroArch on Linux.

        Args:
            retroarch_path: Optional path to RetroArch binary or directory.

        Returns:
            Path to runtime runner script or executable, or None if not located.
        """
        adapter = SteamRetroArchAdapter(configured_path=retroarch_path)
        return adapter.resolve_steam_linux_runtime()

    @classmethod
    def get_or_create_retroarch_wrapper(
        cls,
        retroarch_exe: str,
    ) -> str:
        """Ensure a launch wrapper script exists that sets LD_LIBRARY_PATH for Steam RetroArch on Linux.

        Args:
            retroarch_exe: Path to the RetroArch binary.

        Returns:
            Path to the wrapper script if on Linux, or retroarch_exe if not needed.
        """
        adapter = SteamRetroArchAdapter(configured_path=retroarch_exe)
        return adapter.get_or_create_retroarch_wrapper(Path(retroarch_exe))

    @classmethod
    def launch_game(
        cls,
        rom_path: str,
        platform_slug: str,
        configured_retroarch_path: str = "",
        custom_mappings: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, Optional[subprocess.Popen]]:
        """Launch game with detected RetroArch flavor.

        Args:
            rom_path: Path to target ROM file on disk.
            platform_slug: Target platform identifier.
            configured_retroarch_path: Optional configured RetroArch path.
            custom_mappings: Optional custom core mapping dictionary.

        Returns:
            Tuple of (success_boolean, status_message, spawned_popen_process).
        """
        retroarch_exe = cls.resolve_retroarch_binary(configured_retroarch_path)
        if not retroarch_exe:
            logger.error("Failed to launch game: RetroArch binary not found.")
            return (
                False,
                "RetroArch executable not found. Please set RetroArch Path in Settings.",
                None,
            )

        core_path = cls.resolve_core_path(
            platform_slug, retroarch_exe, custom_mappings
        )
        if not core_path:
            logger.error(
                "Failed to launch game: libretro core for platform '%s' not found.",
                platform_slug,
            )
            return (
                False,
                f"Could not find a valid libretro core for platform '{platform_slug}'.",
                None,
            )

        adapter = get_retroarch_adapter(configured_path=retroarch_exe)
        return adapter.launch_game(
            rom_path=rom_path,
            platform_slug=platform_slug,
            custom_mappings=custom_mappings,
            core_path=core_path,
            binary_path=Path(retroarch_exe),
        )
