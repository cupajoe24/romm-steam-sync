"""Standalone RetroArch adapter.

Encapsulates host filesystem discovery, platform standard paths, and direct process
execution for standalone RetroArch installations across Windows, macOS, and Linux.
"""

import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional

from romm_steam_sync.adapters.retroarch.base import (
    BaseRetroArchAdapter,
    RetroArchFlavor,
)

logger = logging.getLogger(__name__)


class StandaloneRetroArchAdapter(BaseRetroArchAdapter):
    """Adapter for native/standalone installations of RetroArch."""

    @property
    def flavor(self) -> RetroArchFlavor:
        return RetroArchFlavor.STANDALONE

    @property
    def flavor_name(self) -> str:
        return "RetroArch Standalone"

    def resolve_binary(self) -> Optional[Path]:
        """Locate standalone RetroArch executable binary.

        Returns:
            Resolved absolute Path to RetroArch binary or None if not found.
        """
        # 1. Configured path
        if self.configured_path:
            p = Path(self.configured_path)
            if p.is_file():
                return p.resolve()
            if p.is_dir():
                exe_name = "retroarch.exe" if self.os_platform == "win32" else "retroarch"
                cand = p / exe_name
                if cand.is_file():
                    return cand.resolve()
                mac_app = p / "Contents" / "MacOS" / "RetroArch"
                if mac_app.is_file():
                    return mac_app.resolve()

        # 2. Check PATH
        which_path = shutil.which("retroarch")
        if which_path and Path(which_path).is_file():
            return Path(which_path)

        flatpak_which = shutil.which("org.libretro.RetroArch")
        if flatpak_which and Path(flatpak_which).is_file():
            return Path(flatpak_which)

        # 3. Platform default paths
        candidates: List[Path] = []
        if self.os_platform == "win32":
            candidates.extend([
                Path(r"C:\Program Files\RetroArch-Win64\retroarch.exe"),
                Path(r"C:\Program Files (x86)\RetroArch-Win64\retroarch.exe"),
                Path(r"C:\RetroArch-Win64\retroarch.exe"),
            ])
        elif self.os_platform == "darwin":
            candidates.extend([
                Path("/Applications/RetroArch.app/Contents/MacOS/RetroArch"),
                self.home_dir
                / "Applications"
                / "RetroArch.app"
                / "Contents"
                / "MacOS"
                / "RetroArch",
            ])
        else:
            candidates.extend([
                Path("/usr/bin/retroarch"),
                Path("/usr/local/bin/retroarch"),
                Path("/var/lib/flatpak/exports/bin/org.libretro.RetroArch"),
                self.home_dir
                / ".local"
                / "share"
                / "flatpak"
                / "exports"
                / "bin"
                / "org.libretro.RetroArch",
                Path("/snap/bin/retroarch"),
                Path("/var/lib/snapd/snap/bin/retroarch"),
            ])

        for cand in candidates:
            try:
                if cand.is_file():
                    return cand.resolve()
            except Exception as e:
                logger.debug("Error checking standalone candidate %s: %s", cand, e)

        return None

    def resolve_cfg_path(self) -> Optional[Path]:
        """Locate retroarch.cfg across standard platform locations.

        Returns:
            Resolved absolute Path to retroarch.cfg or None.
        """
        if self._cfg_path is not None and self._cfg_path.is_file():
            return self._cfg_path

        candidates: List[Path] = []

        if self.configured_path:
            p = Path(self.configured_path)
            if p.is_file():
                if p.name.lower() == "retroarch.cfg":
                    candidates.append(p)
                else:
                    candidates.append(p.parent / "retroarch.cfg")
            elif p.is_dir():
                candidates.append(p / "retroarch.cfg")

        ra_binary = self.resolve_binary()
        if ra_binary:
            candidates.append(ra_binary.parent / "retroarch.cfg")

        if self.os_platform == "win32":
            candidates.extend([
                self.home_dir / "AppData" / "Roaming" / "RetroArch" / "retroarch.cfg",
                Path(r"C:\Program Files\RetroArch-Win64\retroarch.cfg"),
                Path(r"C:\Program Files (x86)\RetroArch-Win64\retroarch.cfg"),
                Path(r"C:\RetroArch-Win64\retroarch.cfg"),
            ])
        elif self.os_platform == "darwin":
            candidates.extend([
                self.home_dir
                / "Library"
                / "Application Support"
                / "RetroArch"
                / "config"
                / "retroarch.cfg",
                self.home_dir
                / "Library"
                / "Application Support"
                / "RetroArch"
                / "retroarch.cfg",
            ])
        else:
            candidates.extend([
                self.home_dir / ".config" / "retroarch" / "retroarch.cfg",
                self.home_dir
                / ".var"
                / "app"
                / "org.libretro.RetroArch"
                / "config"
                / "retroarch"
                / "retroarch.cfg",
                self.home_dir
                / "snap"
                / "retroarch"
                / "current"
                / ".config"
                / "retroarch"
                / "retroarch.cfg",
            ])

        for cand in candidates:
            try:
                if cand.is_file():
                    self._cfg_path = cand.resolve()
                    return self._cfg_path
            except Exception as e:
                logger.debug("Error checking retroarch.cfg candidate %s: %s", cand, e)

        return None

    def get_core_search_dirs(self) -> List[Path]:
        """Collect directories to search for libretro core libraries.

        Returns:
            List of directory Path objects in priority order.
        """
        search_dirs: List[Path] = []
        ra_binary = self.resolve_binary()
        if ra_binary:
            search_dirs.append(ra_binary.parent / "cores")
            search_dirs.append(ra_binary.parent)
            if self.os_platform == "darwin" and "Contents/MacOS" in str(ra_binary):
                search_dirs.append(ra_binary.parent.parent / "Resources" / "cores")

        if self.os_platform == "win32":
            search_dirs.extend([
                Path(r"C:\Program Files\RetroArch-Win64\cores"),
                Path(r"C:\Program Files (x86)\RetroArch-Win64\cores"),
                Path(r"C:\RetroArch-Win64\cores"),
            ])
        elif self.os_platform == "darwin":
            search_dirs.extend([
                self.home_dir / "Library" / "Application Support" / "RetroArch" / "cores",
                Path("/Applications/RetroArch.app/Contents/Resources/cores"),
                self.home_dir
                / "Applications"
                / "RetroArch.app"
                / "Contents"
                / "Resources"
                / "cores",
            ])
        else:
            search_dirs.extend([
                Path("/usr/lib/libretro"),
                Path("/usr/lib64/libretro"),
                Path("/usr/lib/x86_64-linux-gnu/libretro"),
                Path("/usr/lib/aarch64-linux-gnu/libretro"),
                self.home_dir / ".config" / "retroarch" / "cores",
                self.home_dir
                / ".var"
                / "app"
                / "org.libretro.RetroArch"
                / "config"
                / "retroarch"
                / "cores",
                self.home_dir
                / "snap"
                / "retroarch"
                / "current"
                / ".config"
                / "retroarch"
                / "cores",
            ])

        return search_dirs

    def get_info_search_dirs(self, raw_info_path: str = "") -> List[Path]:
        """Collect directories to search for libretro core .info metadata files.

        Args:
            raw_info_path: Optional raw 'libretro_info_path' setting from retroarch.cfg.

        Returns:
            List of directory Path objects in priority order.
        """
        info_dirs: List[Path] = []
        ra_binary = self.resolve_binary()
        ra_dir = ra_binary.parent if ra_binary else None

        if raw_info_path.startswith(":"):
            sub = raw_info_path.lstrip(":\\/")
            if ra_dir:
                info_dirs.append(ra_dir / sub)
        elif raw_info_path:
            info_dirs.append(
                Path(os.path.expanduser(os.path.expandvars(raw_info_path)))
            )

        if ra_dir:
            info_dirs.extend([
                ra_dir / "info",
                ra_dir / "cores",
            ])

        if self.os_platform == "win32":
            info_dirs.append(
                self.home_dir / "AppData" / "Roaming" / "RetroArch" / "info"
            )
        elif self.os_platform == "darwin":
            info_dirs.append(
                self.home_dir / "Library" / "Application Support" / "RetroArch" / "info"
            )
        else:
            info_dirs.extend([
                self.home_dir / ".config" / "retroarch" / "cores",
                Path("/usr/share/libretro/info"),
                Path("/usr/local/share/libretro/info"),
            ])

        return info_dirs

    def resolve_saves_base_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve base directory for save files in standalone RetroArch.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to the saves root directory.
        """
        if settings is None:
            settings = self.get_config_settings()

        raw_dir = settings.get("savefile_directory", "")
        ra_binary = self.resolve_binary()
        ra_dir = ra_binary.parent if ra_binary else None

        # 1. Handle RetroArch ':' prefix
        if raw_dir.startswith(":"):
            sub = raw_dir.lstrip(":\\/")
            if ra_dir:
                return (ra_dir / sub).resolve()
            if self.os_platform == "win32":
                return (
                    self.home_dir / "AppData" / "Roaming" / "RetroArch" / sub
                ).resolve()
            elif self.os_platform == "darwin":
                return (
                    self.home_dir
                    / "Library"
                    / "Application Support"
                    / "RetroArch"
                    / sub
                ).resolve()
            else:
                return (self.home_dir / ".config" / "retroarch" / sub).resolve()

        # 2. Handle 'default', 'none', or empty
        if not raw_dir or raw_dir.lower() in ("default", "none"):
            if ra_dir and (ra_dir / "saves").is_dir():
                return (ra_dir / "saves").resolve()
            if self.os_platform == "win32":
                return (
                    self.home_dir / "AppData" / "Roaming" / "RetroArch" / "saves"
                ).resolve()
            elif self.os_platform == "darwin":
                return (
                    self.home_dir
                    / "Library"
                    / "Application Support"
                    / "RetroArch"
                    / "saves"
                ).resolve()
            else:
                flatpak_saves = (
                    self.home_dir
                    / ".var"
                    / "app"
                    / "org.libretro.RetroArch"
                    / "config"
                    / "retroarch"
                    / "saves"
                )
                if flatpak_saves.is_dir():
                    return flatpak_saves.resolve()
                return (self.home_dir / ".config" / "retroarch" / "saves").resolve()

        # 3. Explicit path
        expanded = os.path.expanduser(os.path.expandvars(raw_dir))
        p = Path(expanded)
        if not p.is_absolute() and ra_dir:
            return (ra_dir / p).resolve()
        return p.resolve()

    def resolve_states_base_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve base directory for savestates in standalone RetroArch.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to states folder.
        """
        ra_binary = self.resolve_binary()
        ra_dir = ra_binary.parent if ra_binary else None
        if ra_dir and (ra_dir / "states").is_dir():
            return (ra_dir / "states").resolve()

        if self.os_platform == "win32":
            return (
                self.home_dir / "AppData" / "Roaming" / "RetroArch" / "states"
            ).resolve()
        elif self.os_platform == "darwin":
            return (
                self.home_dir
                / "Library"
                / "Application Support"
                / "RetroArch"
                / "states"
            ).resolve()
        else:
            return (self.home_dir / ".config" / "retroarch" / "states").resolve()

    def resolve_system_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve base directory for BIOS/system files in standalone RetroArch.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to system folder.
        """
        ra_binary = self.resolve_binary()
        ra_dir = ra_binary.parent if ra_binary else None
        if ra_dir and (ra_dir / "system").is_dir():
            return (ra_dir / "system").resolve()

        if self.os_platform == "win32":
            return (
                self.home_dir / "AppData" / "Roaming" / "RetroArch" / "system"
            ).resolve()
        elif self.os_platform == "darwin":
            return (
                self.home_dir
                / "Library"
                / "Application Support"
                / "RetroArch"
                / "system"
            ).resolve()
        else:
            return (self.home_dir / ".config" / "retroarch" / "system").resolve()

    def build_launch_command(
        self,
        rom_path: str,
        core_path: str,
        binary_path: Optional[Path] = None,
    ) -> List[str]:
        """Construct the subprocess argument list to launch standalone RetroArch.

        Args:
            rom_path: Absolute path to ROM file.
            core_path: Path or identifier of libretro core.
            binary_path: Optional pre-resolved binary path.

        Returns:
            List of command line string arguments.
        """
        binary = binary_path or self.resolve_binary()
        if not binary:
            return []

        return [str(binary), "-L", core_path, rom_path]
