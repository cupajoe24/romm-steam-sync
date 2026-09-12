"""Steam version of RetroArch (AppID 1118310) adapter.

Encapsulates Steam library discovery, Steam Linux Runtime (Pressure Vessel) container
wrapping, libmist.so library path resolution, and Steam RetroArch directory hierarchy.
"""

import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from romm_steam_sync.adapters.retroarch.base import (
    BaseRetroArchAdapter,
    RetroArchFlavor,
)
from romm_steam_sync.adapters.steam_path import SteamPathResolver

logger = logging.getLogger(__name__)


class SteamRetroArchAdapter(BaseRetroArchAdapter):
    """Adapter for RetroArch installed and distributed via Steam."""

    STEAM_APP_ID = 1118310

    @property
    def flavor(self) -> RetroArchFlavor:
        return RetroArchFlavor.STEAM

    @property
    def flavor_name(self) -> str:
        return "RetroArch Steam"

    def resolve_binary(self) -> Optional[Path]:
        """Locate RetroArch executable binary within Steam library folders.

        Returns:
            Resolved absolute Path to Steam RetroArch binary or None if not located.
        """
        # 1. Configured path if provided and valid
        if self.configured_path:
            p = Path(self.configured_path)
            if p.is_file():
                return p.resolve()
            if p.is_dir():
                exe_name = "retroarch.exe" if self.os_platform == "win32" else "retroarch"
                cand = p / exe_name
                if cand.is_file():
                    return cand.resolve()
                mac_cand = p / "Contents" / "MacOS" / "RetroArch"
                if mac_cand.is_file():
                    return mac_cand.resolve()

        # 2. Inspect Steam library folders
        candidates: List[Path] = []
        try:
            exe_name = "retroarch.exe" if self.os_platform == "win32" else "retroarch"
            steam_root = SteamPathResolver.get_steam_root()
            if steam_root:
                candidates.append(
                    steam_root / "steamapps" / "common" / "RetroArch" / exe_name
                )
                if self.os_platform == "darwin":
                    candidates.append(
                        steam_root
                        / "steamapps"
                        / "common"
                        / "RetroArch"
                        / "RetroArch.app"
                        / "Contents"
                        / "MacOS"
                        / "RetroArch"
                    )

            library_folders = SteamPathResolver.get_library_folders()
            for lib_dir in library_folders:
                candidates.append(
                    lib_dir / "steamapps" / "common" / "RetroArch" / exe_name
                )
                if self.os_platform == "darwin":
                    candidates.append(
                        lib_dir
                        / "steamapps"
                        / "common"
                        / "RetroArch"
                        / "RetroArch.app"
                        / "Contents"
                        / "MacOS"
                        / "RetroArch"
                    )
        except Exception as e:
            logger.debug("Error querying Steam path resolver for RetroArch: %s", e)

        for cand in candidates:
            try:
                if cand.is_file():
                    return cand.resolve()
            except Exception as e:
                logger.debug("Error checking candidate %s: %s", cand, e)

        return None

    def resolve_cfg_path(self) -> Optional[Path]:
        """Locate retroarch.cfg inside Steam RetroArch directory.

        Returns:
            Resolved absolute Path to retroarch.cfg or None.
        """
        if self._cfg_path is not None and self._cfg_path.is_file():
            return self._cfg_path

        if self.configured_path:
            p = Path(self.configured_path)
            if p.is_file():
                if p.name.lower() == "retroarch.cfg":
                    self._cfg_path = p.resolve()
                    return self._cfg_path
                cand = p.parent / "retroarch.cfg"
                if cand.is_file():
                    self._cfg_path = cand.resolve()
                    return self._cfg_path
            elif p.is_dir():
                cand = p / "retroarch.cfg"
                if cand.is_file():
                    self._cfg_path = cand.resolve()
                    return self._cfg_path

        ra_binary = self.resolve_binary()
        if ra_binary:
            cand = ra_binary.parent / "retroarch.cfg"
            if cand.is_file():
                self._cfg_path = cand.resolve()
                return self._cfg_path

        return None

    def get_core_search_dirs(self) -> List[Path]:
        """Collect cores directories within Steam RetroArch install.

        Returns:
            List of directory Path objects in priority search order.
        """
        search_dirs: List[Path] = []
        ra_binary = self.resolve_binary()
        if ra_binary:
            ra_dir = ra_binary.parent
            search_dirs.append(ra_dir / "cores")
            search_dirs.append(ra_dir)
            if self.os_platform == "darwin" and "Contents/MacOS" in str(ra_binary):
                search_dirs.append(ra_dir.parent / "Resources" / "cores")

        return search_dirs

    def get_info_search_dirs(self, raw_info_path: str = "") -> List[Path]:
        """Collect .info directories within Steam RetroArch install.

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

        return info_dirs

    def resolve_saves_base_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve base directory for save files in Steam RetroArch.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to saves folder.
        """
        if settings is None:
            settings = self.get_config_settings()

        raw_dir = settings.get("savefile_directory", "")
        ra_binary = self.resolve_binary()
        ra_dir = ra_binary.parent if ra_binary else None

        if raw_dir.startswith(":"):
            sub = raw_dir.lstrip(":\\/")
            if ra_dir:
                return (ra_dir / sub).resolve()

        if not raw_dir or raw_dir.lower() in ("default", "none"):
            if ra_dir and (ra_dir / "saves").is_dir():
                return (ra_dir / "saves").resolve()
            if ra_dir:
                return (ra_dir / "saves").resolve()

        expanded = os.path.expanduser(os.path.expandvars(raw_dir))
        p = Path(expanded)
        if not p.is_absolute() and ra_dir:
            return (ra_dir / p).resolve()
        return p.resolve()

    def resolve_states_base_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve base directory for savestates in Steam RetroArch.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to states folder.
        """
        ra_binary = self.resolve_binary()
        ra_dir = ra_binary.parent if ra_binary else None
        if ra_dir:
            return (ra_dir / "states").resolve()
        return self.home_dir / "states"

    def resolve_system_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve base directory for BIOS/system files in Steam RetroArch.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to system folder.
        """
        ra_binary = self.resolve_binary()
        ra_dir = ra_binary.parent if ra_binary else None
        if ra_dir:
            return (ra_dir / "system").resolve()
        return self.home_dir / "system"

    def resolve_steam_linux_runtime(
        self, binary_path: Optional[Path] = None
    ) -> Optional[Path]:
        """Locate Steam Linux Runtime runner script for Steam RetroArch on Linux.

        Args:
            binary_path: Optional pre-resolved binary path.

        Returns:
            Path to runtime runner script or executable, or None if not located.
        """
        if not self.os_platform.startswith("linux"):
            return None

        candidates: List[Path] = []
        ra_binary = binary_path or self.resolve_binary()
        if ra_binary:
            common_dir = ra_binary.parent.parent
            candidates.extend([
                common_dir / "SteamLinuxRuntime_sniper" / "run",
                common_dir / "SteamLinuxRuntime_sniper" / "_v2-entry-point",
                common_dir / "SteamLinuxRuntime_soldier" / "run",
                common_dir / "SteamLinuxRuntime_soldier" / "_v2-entry-point",
                common_dir / "SteamLinuxRuntime" / "run",
            ])

        try:
            library_folders = SteamPathResolver.get_library_folders()
            for lib_root in library_folders:
                common_dir = lib_root / "steamapps" / "common"
                candidates.extend([
                    common_dir / "SteamLinuxRuntime_sniper" / "run",
                    common_dir / "SteamLinuxRuntime_sniper" / "_v2-entry-point",
                    common_dir / "SteamLinuxRuntime_soldier" / "run",
                    common_dir / "SteamLinuxRuntime_soldier" / "_v2-entry-point",
                    common_dir / "SteamLinuxRuntime" / "run",
                ])
                candidates.append(
                    lib_root / "ubuntu12_32" / "steam-runtime" / "run.sh"
                )
        except Exception as e:
            logger.debug(
                "Error inspecting Steam library folders for Linux runtime: %s", e
            )

        for cand in candidates:
            try:
                if cand.is_file():
                    return cand.resolve()
            except Exception as e:
                logger.debug("Error checking runtime candidate %s: %s", cand, e)

        return None

    def get_or_create_retroarch_wrapper(self, retroarch_exe: Path) -> str:
        """Ensure a launch wrapper script exists setting LD_LIBRARY_PATH on Linux.

        Args:
            retroarch_exe: Path to the RetroArch binary.

        Returns:
            Path to the wrapper script if on Linux, or raw binary path string.
        """
        if not self.os_platform.startswith("linux"):
            return str(retroarch_exe)

        ra_dir = retroarch_exe.parent

        # Prevent Mist stdin crash by removing leftover steam_appid.txt
        try:
            appid_file = ra_dir / "steam_appid.txt"
            if appid_file.is_file():
                appid_file.unlink()
                logger.info("Removed %s to prevent Mist stdin crash", appid_file)
        except Exception as e:
            logger.debug("Could not remove %s: %s", appid_file, e)

        script_content = (
            "#!/bin/sh\n"
            'DIR="$(cd "$(dirname "$0")" && pwd)"\n'
            'export LD_LIBRARY_PATH="$DIR:${LD_LIBRARY_PATH:-}"\n'
            f'exec "$DIR/{retroarch_exe.name}" "$@"\n'
        )

        existing_sh = ra_dir / "retroarch.sh"
        if existing_sh.is_file():
            try:
                sh_text = existing_sh.read_text(encoding="utf-8")
                if "SteamAppId" in sh_text:
                    existing_sh.write_text(script_content, encoding="utf-8")
                    logger.info("Updated existing wrapper script to remove SteamAppId: %s", existing_sh)
                existing_sh.chmod(existing_sh.stat().st_mode | 0o111)
                logger.info("Using existing RetroArch wrapper script: %s", existing_sh)
                return str(existing_sh.resolve())
            except Exception as e:
                logger.debug("Could not inspect or chmod existing %s: %s", existing_sh, e)
                return str(existing_sh.resolve())

        try:
            target_sh = ra_dir / "retroarch.sh"
            target_sh.write_text(script_content, encoding="utf-8")
            target_sh.chmod(target_sh.stat().st_mode | 0o111)
            logger.info("Created RetroArch launch wrapper script at %s", target_sh)
            return str(target_sh.resolve())
        except Exception as e:
            logger.debug("Cannot write wrapper script to %s: %s", ra_dir, e)

        try:
            from romm_steam_sync.config import get_default_config_dir

            bin_dir = get_default_config_dir() / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            fallback_sh = bin_dir / "run_retroarch.sh"
            fallback_content = (
                "#!/bin/sh\n"
                f'RA_DIR="{str(ra_dir.resolve())}"\n'
                'export LD_LIBRARY_PATH="$RA_DIR:${LD_LIBRARY_PATH:-}"\n'
                f'exec "$RA_DIR/{retroarch_exe.name}" "$@"\n'
            )
            fallback_sh.write_text(fallback_content, encoding="utf-8")
            fallback_sh.chmod(fallback_sh.stat().st_mode | 0o111)
            logger.info(
                "Created fallback RetroArch launch wrapper script at %s",
                fallback_sh,
            )
            return str(fallback_sh.resolve())
        except Exception as e:
            logger.warning(
                "Failed creating RetroArch wrapper script: %s. Using raw binary.",
                e,
            )
            return str(retroarch_exe)

    def build_launch_command(
        self,
        rom_path: str,
        core_path: str,
        binary_path: Optional[Path] = None,
    ) -> List[str]:
        """Construct the subprocess argument list to launch a game via Steam RetroArch.

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

        if self.os_platform.startswith("linux"):
            target_exe = self.get_or_create_retroarch_wrapper(binary)
            runtime_runner = self.resolve_steam_linux_runtime(binary_path=binary)
            if runtime_runner:
                logger.info(
                    "Detected Steam RetroArch build on Linux. Wrapping command with Steam Linux Runtime: %s",
                    runtime_runner,
                )
                if runtime_runner.name == "run.sh":
                    return [str(runtime_runner), target_exe, "-L", core_path, rom_path]
                return [str(runtime_runner), "--", target_exe, "-L", core_path, rom_path]
            return [target_exe, "-L", core_path, rom_path]

        return [str(binary), "-L", core_path, rom_path]

    def prepare_launch_environment(
        self,
        rom_path: str,
        core_path: str,
        binary_path: Optional[Path] = None,
    ) -> Dict[str, str]:
        """Prepare environment variables with Pressure Vessel mounts for Steam on Linux.

        Args:
            rom_path: Path to target ROM.
            core_path: Path to target core.
            binary_path: Optional pre-resolved binary path.

        Returns:
            Environment variables dictionary.
        """
        env = super().prepare_launch_environment(rom_path, core_path, binary_path)
        if not self.os_platform.startswith("linux"):
            return env

        binary = binary_path or self.resolve_binary()
        if not binary:
            return env

        try:
            ra_dir_str = str(binary.parent)
            current_ld = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = (
                f"{ra_dir_str}:{current_ld}" if current_ld else ra_dir_str
            )

            rom_dir = str(Path(rom_path).resolve().parent)
            core_dir = str(Path(core_path).resolve().parent)
            extra_mounts = [rom_dir, core_dir, ra_dir_str]

            for sub_name in ["saves", "system"]:
                cand_sub = binary.parent / sub_name
                if cand_sub.is_dir() and str(cand_sub) not in extra_mounts:
                    extra_mounts.append(str(cand_sub))

            home_ra = self.home_dir / ".config" / "retroarch"
            if home_ra.is_dir() and str(home_ra) not in extra_mounts:
                extra_mounts.append(str(home_ra))

            existing_rw = env.get("PRESSURE_VESSEL_FILESYSTEMS_RW", "")
            if existing_rw:
                extra_mounts.insert(0, existing_rw)
            env["PRESSURE_VESSEL_FILESYSTEMS_RW"] = ":".join(extra_mounts)

            existing_compat = env.get("STEAM_COMPAT_MOUNTS", "")
            if existing_compat:
                extra_mounts.insert(0, existing_compat)
            env["STEAM_COMPAT_MOUNTS"] = ":".join(extra_mounts)
        except Exception as e:
            logger.debug(
                "Failed configuring pressure-vessel mount environment variables: %s",
                e,
            )

        return env
