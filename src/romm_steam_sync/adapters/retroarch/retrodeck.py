"""RetroDECK Flatpak emulation environment adapter.

Encapsulates retrodeck.json configuration parsing, dynamic home and SD card path resolution,
Flatpak command invocation, and RetroDECK-specific content-sorted save directory layout.
"""

from enum import Enum
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any, Dict, List, Optional

from romm_steam_sync.adapters.retroarch.base import (
    BaseRetroArchAdapter,
    RetroArchFlavor,
)

logger = logging.getLogger(__name__)


class RetroDeckConfigHealth(Enum):
    """Health classification for RetroDECK configuration state."""

    OK = "OK"
    ABSENT = "ABSENT"
    UNREADABLE = "UNREADABLE"
    ROOT_MISSING = "ROOT_MISSING"


class RetroDeckAdapter(BaseRetroArchAdapter):
    """Adapter for RetroArch executing inside the RetroDECK Flatpak environment."""

    FLATPAK_APP_ID = "net.retrodeck.retrodeck"
    _CACHE_TTL_SECONDS = 30.0

    def __init__(
        self,
        configured_path: str = "",
        os_platform: Optional[str] = None,
        home_dir: Optional[Path] = None,
    ) -> None:
        """Initialize RetroDECK adapter.

        Args:
            configured_path: User-configured path to RetroDECK or RetroArch binary.
            os_platform: Optional OS identifier ('win32', 'darwin', 'linux').
            home_dir: Optional user home directory Path.
        """
        super().__init__(
            configured_path=configured_path,
            os_platform=os_platform,
            home_dir=home_dir,
        )
        self._cached_rd_config: Optional[Dict[str, Any]] = None
        self._cache_time: float = 0.0
        self._last_health: RetroDeckConfigHealth = RetroDeckConfigHealth.ABSENT

    @property
    def flavor(self) -> RetroArchFlavor:
        return RetroArchFlavor.RETRODECK

    @property
    def flavor_name(self) -> str:
        return "RetroDECK"

    def get_default_sort_by_content(self) -> bool:
        """Get the RetroDECK default for sort_savefiles_by_content_enable.

        Returns:
            True: RetroDECK default layout places saves in system/content folders.
        """
        return True

    def retrodeck_json_path(self) -> Path:
        """Get the filesystem path to retrodeck.json.

        Returns:
            Path object pointing to retrodeck.json.
        """
        return (
            self.home_dir
            / ".var"
            / "app"
            / self.FLATPAK_APP_ID
            / "config"
            / "retrodeck"
            / "retrodeck.json"
        )

    def load_retrodeck_config(self) -> Optional[Dict[str, Any]]:
        """Load and cache retrodeck.json settings with a 30-second TTL.

        Returns:
            Parsed dictionary from retrodeck.json, or None if missing/unreadable.
        """
        now = time.monotonic()
        if (
            self._cached_rd_config is not None
            and (now - self._cache_time) < self._CACHE_TTL_SECONDS
        ):
            return self._cached_rd_config

        json_file = self.retrodeck_json_path()
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cached_rd_config = data
            self._cache_time = now
            self._last_health = RetroDeckConfigHealth.OK
            return data
        except FileNotFoundError:
            self._cached_rd_config = None
            self._last_health = RetroDeckConfigHealth.ABSENT
            return None
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to parse RetroDECK config at %s: %s", json_file, e)
            self._cached_rd_config = None
            self._cache_time = now
            self._last_health = RetroDeckConfigHealth.UNREADABLE
            return None

    def config_health(self) -> RetroDeckConfigHealth:
        """Classify the health and accessibility of RetroDECK configuration.

        Returns:
            RetroDeckConfigHealth enum member.
        """
        self.load_retrodeck_config()
        if self._last_health in (
            RetroDeckConfigHealth.ABSENT,
            RetroDeckConfigHealth.UNREADABLE,
        ):
            return self._last_health

        home_dir = self.retrodeck_home()
        if not home_dir.is_dir():
            return RetroDeckConfigHealth.ROOT_MISSING

        return RetroDeckConfigHealth.OK

    def _get_rd_path(self, key: str, fallback_subdir: str) -> Path:
        """Retrieve a specific directory from retrodeck.json paths, with fallback.

        Args:
            key: Path key inside retrodeck.json 'paths' object.
            fallback_subdir: Fallback subdirectory name under ~/retrodeck.

        Returns:
            Resolved absolute Path.
        """
        config = self.load_retrodeck_config()
        if config and isinstance(config, dict):
            paths = config.get("paths", {})
            if isinstance(paths, dict):
                raw = paths.get(key, "")
                if raw:
                    return Path(os.path.expanduser(raw)).resolve()

        return (self.home_dir / "retrodeck" / fallback_subdir).resolve()

    def retrodeck_home(self) -> Path:
        """Get the base RetroDECK home directory.

        Returns:
            Resolved Path to RetroDECK home folder.
        """
        config = self.load_retrodeck_config()
        if config and isinstance(config, dict):
            paths = config.get("paths", {})
            if isinstance(paths, dict):
                raw = paths.get("rd_home_path", "")
                if raw:
                    return Path(os.path.expanduser(raw)).resolve()

        return (self.home_dir / "retrodeck").resolve()

    def roms_path(self) -> Path:
        """Get the RetroDECK ROMs base directory.

        Returns:
            Resolved Path to ROMs folder.
        """
        return self._get_rd_path("roms_path", "roms")

    def bios_path(self) -> Path:
        """Get the RetroDECK BIOS / system directory.

        Returns:
            Resolved Path to BIOS folder.
        """
        return self._get_rd_path("bios_path", "bios")

    def resolve_binary(self) -> Optional[Path]:
        """Locate RetroArch executable or Flatpak binary for RetroDECK.

        Returns:
            Path to RetroArch executable, Flatpak command, or None.
        """
        if self.configured_path:
            p = Path(self.configured_path)
            if p.is_file():
                return p.resolve()
            if p.is_dir():
                cand = p / "retroarch"
                if cand.is_file():
                    return cand.resolve()

        # If inside RetroDECK Flatpak container
        if self.os_platform.startswith("linux") and os.path.exists("/.flatpak-info"):
            for in_sandbox_ra in (
                Path("/app/retrodeck/components/retroarch/bin/retroarch"),
                Path("/app/bin/retroarch"),
            ):
                if in_sandbox_ra.is_file():
                    return in_sandbox_ra.resolve()

        # Check host flatpak runner
        flatpak_bin = shutil.which("flatpak")
        if flatpak_bin and Path(flatpak_bin).is_file():
            return Path(flatpak_bin).resolve()

        return None

    def resolve_cfg_path(self) -> Optional[Path]:
        """Locate retroarch.cfg for RetroArch within RetroDECK.

        Returns:
            Path to retroarch.cfg inside RetroDECK configuration directory.
        """
        if self._cfg_path is not None and self._cfg_path.is_file():
            return self._cfg_path

        candidates = [
            self.home_dir
            / ".var"
            / "app"
            / self.FLATPAK_APP_ID
            / "config"
            / "retroarch"
            / "retroarch.cfg",
            self.retrodeck_home() / ".config" / "retroarch" / "retroarch.cfg",
        ]

        if self.configured_path:
            p = Path(self.configured_path)
            if p.is_file():
                if p.name.lower() == "retroarch.cfg":
                    candidates.insert(0, p)
                else:
                    candidates.insert(0, p.parent / "retroarch.cfg")
            elif p.is_dir():
                candidates.insert(0, p / "retroarch.cfg")

        for cand in candidates:
            if cand.is_file():
                self._cfg_path = cand.resolve()
                return self._cfg_path

        return None

    def get_core_search_dirs(self) -> List[Path]:
        """Collect directories to search for RetroDECK libretro cores.

        Returns:
            List of search paths.
        """
        return [
            self.home_dir
            / ".var"
            / "app"
            / self.FLATPAK_APP_ID
            / "config"
            / "retroarch"
            / "cores",
            Path("/app/lib/libretro"),
            self.home_dir / ".config" / "retroarch" / "cores",
        ]

    def get_info_search_dirs(self, raw_info_path: str = "") -> List[Path]:
        """Collect directories to search for RetroDECK libretro .info metadata.

        Args:
            raw_info_path: Optional raw 'libretro_info_path' setting from retroarch.cfg.

        Returns:
            List of directory Path objects.
        """
        info_dirs = [
            self.home_dir
            / ".var"
            / "app"
            / self.FLATPAK_APP_ID
            / "config"
            / "retroarch"
            / "cores",
            Path("/app/share/libretro/info"),
            Path("/usr/share/libretro/info"),
        ]
        if raw_info_path:
            expanded = Path(os.path.expanduser(os.path.expandvars(raw_info_path)))
            if expanded not in info_dirs:
                info_dirs.insert(0, expanded)
        return info_dirs

    def resolve_saves_base_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve base directory for save files in RetroDECK.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to the saves root directory.
        """
        return self._get_rd_path("saves_path", "saves")

    def resolve_states_base_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve base directory for savestates in RetroDECK.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to states folder.
        """
        return self._get_rd_path("states_path", "states")

    def resolve_system_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve base directory for BIOS/system files in RetroDECK.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to BIOS folder.
        """
        return self.bios_path()

    def build_launch_command(
        self,
        rom_path: str,
        core_path: str,
        binary_path: Optional[Path] = None,
    ) -> List[str]:
        """Construct the subprocess argument list to launch RetroArch via RetroDECK.

        Uses Flatpak CLI if running from host, or direct binary if inside container.

        Args:
            rom_path: Absolute path to ROM file.
            core_path: Path or identifier of libretro core.
            binary_path: Optional pre-resolved binary path.

        Returns:
            List of command line string arguments.
        """
        if binary_path and binary_path.name.lower() in ("retroarch", "retroarch.exe"):
            return [str(binary_path), "-L", core_path, rom_path]

        if self.os_platform.startswith("linux") and os.path.exists("/.flatpak-info"):
            for in_sandbox_ra in (
                Path("/app/retrodeck/components/retroarch/bin/retroarch"),
                Path("/app/bin/retroarch"),
            ):
                if in_sandbox_ra.is_file():
                    return [str(in_sandbox_ra), "-L", core_path, rom_path]

        flatpak_bin = shutil.which("flatpak") or "flatpak"
        return [
            flatpak_bin,
            "run",
            self.FLATPAK_APP_ID,
            "--open",
            "retroarch",
            "-L",
            core_path,
            rom_path,
        ]
