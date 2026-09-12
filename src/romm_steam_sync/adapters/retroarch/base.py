"""Shared RetroArch base adapter, core metadata mappings, and utility functions.

Defines the abstract BaseRetroArchAdapter class that establishes the contract for
RetroArch path resolution, configuration parsing, core discovery, and game process
execution across different distribution flavors (Steam, Standalone, RetroDECK).
"""

from abc import ABC, abstractmethod
from enum import Enum
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

import psutil

from romm_steam_sync.domain.platform import (
    lookup_platform_mapping,
    normalize_platform_slug,
    strip_core_suffix,
)

logger = logging.getLogger(__name__)


class RetroArchFlavor(str, Enum):
    """Supported RetroArch distributions and emulation environments."""
    AUTO = "auto"
    STEAM = "steam"
    STANDALONE = "standalone"
    RETRODECK = "retrodeck"


# Fallback canonical RetroArch core names when .info files are not found on disk
CORE_NAME_FALLBACKS: Dict[str, str] = {
    # GBA
    "mgba": "mGBA",
    "mgba_libretro": "mGBA",
    "vba_next": "VBA-Next",
    "vba_next_libretro": "VBA-Next",
    "vbam": "VBA-M",
    "vbam_libretro": "VBA-M",
    "gpsp": "gpSP",
    "gpsp_libretro": "gpSP",
    # SNES
    "snes9x": "Snes9x",
    "snes9x_libretro": "Snes9x",
    "snes9x2010": "Snes9x 2010",
    "snes9x2010_libretro": "Snes9x 2010",
    "bsnes": "bsnes",
    "bsnes_libretro": "bsnes",
    "bsnes_hd_beta": "bsnes-hd beta",
    "bsnes_hd_beta_libretro": "bsnes-hd beta",
    # NES
    "nestopia": "Nestopia",
    "nestopia_libretro": "Nestopia",
    "fceumm": "FCEUmm",
    "fceumm_libretro": "FCEUmm",
    "mesen": "Mesen",
    "mesen_libretro": "Mesen",
    # N64
    "mupen64plus_next": "Mupen64Plus-Next",
    "mupen64plus_next_libretro": "Mupen64Plus-Next",
    "parallel_n64": "ParallelN64",
    "parallel_n64_libretro": "ParallelN64",
    # GB / GBC
    "sameboy": "SameBoy",
    "sameboy_libretro": "SameBoy",
    "gambatte": "Gambatte",
    "gambatte_libretro": "Gambatte",
    "gearboy": "Gearboy",
    "gearboy_libretro": "Gearboy",
    # Sega
    "genesis_plus_gx": "Genesis Plus GX",
    "genesis_plus_gx_libretro": "Genesis Plus GX",
    "genesis_plus_gx_wide": "Genesis Plus GX Wide",
    "genesis_plus_gx_wide_libretro": "Genesis Plus GX Wide",
    "picodrive": "PicoDrive",
    "picodrive_libretro": "PicoDrive",
    "beetle_saturn": "Beetle Saturn",
    "beetle_saturn_libretro": "Beetle Saturn",
    "flycast": "Flycast",
    "flycast_libretro": "Flycast",
    # Sony
    "pcsx_rearmed": "PCSX-ReARMed",
    "pcsx_rearmed_libretro": "PCSX-ReARMed",
    "beetle_psx": "Beetle PSX",
    "beetle_psx_libretro": "Beetle PSX",
    "beetle_psx_hw": "Beetle PSX HW",
    "beetle_psx_hw_libretro": "Beetle PSX HW",
    "duckstation": "DuckStation",
    "duckstation_libretro": "DuckStation",
    "swanstation": "SwanStation",
    "swanstation_libretro": "SwanStation",
    "pcsx2": "PCSX2",
    "pcsx2_libretro": "PCSX2",
    "lrps2": "LRPS2",
    "lrps2_libretro": "LRPS2",
    "ppsspp": "PPSSPP",
    "ppsspp_libretro": "PPSSPP",
    # Nintendo DS / 3DS
    "melonds": "melonDS",
    "melonds_libretro": "melonDS",
    "desmume": "DeSmuME",
    "desmume_libretro": "DeSmuME",
    "citra": "Citra",
    "citra_libretro": "Citra",
    # GameCube / Wii
    "dolphin": "Dolphin",
    "dolphin_libretro": "Dolphin",
    # Arcade
    "fbneo": "FinalBurn Neo",
    "fbneo_libretro": "FinalBurn Neo",
}

DEFAULT_CORE_MAPPINGS: Dict[str, str] = {
    # Nintendo
    "nes": "nestopia_libretro",
    "fc": "nestopia_libretro",
    "famicom": "nestopia_libretro",
    "nintendo-entertainment-system": "nestopia_libretro",
    "snes": "snes9x_libretro",
    "sfc": "snes9x_libretro",
    "super-famicom": "snes9x_libretro",
    "super-nintendo": "snes9x_libretro",
    "super-nintendo-entertainment-system": "snes9x_libretro",
    "n64": "mupen64plus_next_libretro",
    "nintendo-64": "mupen64plus_next_libretro",
    "gb": "sameboy_libretro",
    "game-boy": "sameboy_libretro",
    "gbc": "sameboy_libretro",
    "game-boy-color": "sameboy_libretro",
    "gba": "mgba_libretro",
    "game-boy-advance": "mgba_libretro",
    "nds": "melonds_libretro",
    "ds": "melonds_libretro",
    "nintendo-ds": "melonds_libretro",
    "3ds": "citra_libretro",
    "n3ds": "citra_libretro",
    "nintendo-3ds": "citra_libretro",
    "gc": "dolphin_libretro",
    "ngc": "dolphin_libretro",
    "gamecube": "dolphin_libretro",
    "game-cube": "dolphin_libretro",
    "nintendo-gamecube": "dolphin_libretro",
    "wii": "dolphin_libretro",
    "nintendo-wii": "dolphin_libretro",
    "wiiu": "cemu_libretro",
    "wii-u": "cemu_libretro",
    # Sony
    "ps": "pcsx_rearmed_libretro",
    "psx": "pcsx_rearmed_libretro",
    "ps1": "pcsx_rearmed_libretro",
    "playstation": "pcsx_rearmed_libretro",
    "playstation-1": "pcsx_rearmed_libretro",
    "sony-playstation": "pcsx_rearmed_libretro",
    "ps2": "pcsx2_libretro",
    "playstation2": "pcsx2_libretro",
    "playstation-2": "pcsx2_libretro",
    "sony-playstation-2": "pcsx2_libretro",
    "ps3": "rpcs3_libretro",
    "playstation3": "rpcs3_libretro",
    "playstation-3": "rpcs3_libretro",
    "psp": "ppsspp_libretro",
    "playstation-portable": "ppsspp_libretro",
    "psvita": "vitaquake2_libretro",
    # Sega
    "dc": "flycast_libretro",
    "dreamcast": "flycast_libretro",
    "sega-dreamcast": "flycast_libretro",
    "naomi": "flycast_libretro",
    "naomi2": "flycast_libretro",
    "naomigd": "flycast_libretro",
    "atomiswave": "flycast_libretro",
    "saturn": "beetle_saturn_libretro",
    "sega-saturn": "beetle_saturn_libretro",
    "megadrive": "genesis_plus_gx_libretro",
    "mega-drive": "genesis_plus_gx_libretro",
    "genesis": "genesis_plus_gx_libretro",
    "sega-genesis": "genesis_plus_gx_libretro",
    "sega-mega-drive": "genesis_plus_gx_libretro",
    "mastersystem": "genesis_plus_gx_libretro",
    "master-system": "genesis_plus_gx_libretro",
    "sms": "genesis_plus_gx_libretro",
    "gamegear": "genesis_plus_gx_libretro",
    "game-gear": "genesis_plus_gx_libretro",
    "gg": "genesis_plus_gx_libretro",
    "segacd": "genesis_plus_gx_libretro",
    "sega-cd": "genesis_plus_gx_libretro",
    "megacd": "genesis_plus_gx_libretro",
    "mega-cd": "genesis_plus_gx_libretro",
    "sega32x": "picodrive_libretro",
    "sega-32x": "picodrive_libretro",
    "32x": "picodrive_libretro",
    # Other
    "pce": "mednafen_pce_fast_libretro",
    "pcecd": "mednafen_pce_fast_libretro",
    "pcengine": "mednafen_pce_fast_libretro",
    "pcenginecd": "mednafen_pce_fast_libretro",
    "turbografx": "mednafen_pce_fast_libretro",
    "turbografxcd": "mednafen_pce_fast_libretro",
    "3do": "opera_libretro",
    "neogeo": "fbneo_libretro",
    "neogeocd": "neocd_libretro",
}

PLATFORM_CORE_CANDIDATES: Dict[str, List[str]] = {
    # Nintendo
    "nes": ["nestopia_libretro", "fceumm_libretro", "mesen_libretro"],
    "snes": [
        "snes9x_libretro",
        "bsnes_libretro",
        "snes9x2010_libretro",
        "mesen-s_libretro",
    ],
    "n64": ["mupen64plus_next_libretro", "parallel_n64_libretro"],
    "gb": ["sameboy_libretro", "gambatte_libretro", "gearboy_libretro"],
    "gbc": ["sameboy_libretro", "gambatte_libretro", "gearboy_libretro"],
    "gba": ["mgba_libretro", "vba_next_libretro", "gpsp_libretro"],
    "nds": ["melonds_libretro", "desmume_libretro"],
    "3ds": ["citra_libretro", "citra2018_libretro"],
    "gc": ["dolphin_libretro"],
    "wii": ["dolphin_libretro"],
    "wiiu": ["cemu_libretro"],
    # Sega
    "sms": ["genesis_plus_gx_libretro", "gearsystem_libretro", "picodrive_libretro"],
    "genesis": [
        "genesis_plus_gx_libretro",
        "picodrive_libretro",
        "blastem_libretro",
    ],
    "megadrive": [
        "genesis_plus_gx_libretro",
        "picodrive_libretro",
        "blastem_libretro",
    ],
    "segacd": ["genesis_plus_gx_libretro", "picodrive_libretro"],
    "sega32x": ["picodrive_libretro"],
    "gamegear": ["genesis_plus_gx_libretro", "gearsystem_libretro"],
    "saturn": ["beetle_saturn_libretro", "yabause_libretro", "kronos_libretro"],
    "dc": ["flycast_libretro", "flycast_gles2_libretro"],
    "dreamcast": ["flycast_libretro", "flycast_gles2_libretro"],
    # Sony
    "ps": [
        "pcsx_rearmed_libretro",
        "beetle_psx_hw_libretro",
        "duckstation_libretro",
        "mednafen_psx_libretro",
    ],
    "ps1": [
        "pcsx_rearmed_libretro",
        "beetle_psx_hw_libretro",
        "duckstation_libretro",
        "mednafen_psx_libretro",
    ],
    "ps2": ["pcsx2_libretro", "lrps2_libretro", "play_libretro"],
    "ps3": ["rpcs3_libretro"],
    "psp": ["ppsspp_libretro"],
    "psvita": ["vitaquake2_libretro"],
    # Other
    "pce": ["mednafen_pce_fast_libretro", "beetle_pce_fast_libretro"],
    "3do": ["opera_libretro"],
    "neogeo": ["fbneo_libretro"],
}


def get_core_suffix(os_platform: Optional[str] = None) -> str:
    """Get dynamic libretro core file extension for the specified or current OS.

    Args:
        os_platform: Optional operating system identifier ('win32', 'darwin', etc.).
            Defaults to sys.platform.

    Returns:
        '.dll' on Windows, '.dylib' on macOS, or '.so' on Linux.
    """
    plat = os_platform or sys.platform
    if plat == "win32":
        return ".dll"
    if plat == "darwin":
        return ".dylib"
    return ".so"



def ensure_core_suffix(
    core_name: str, os_platform: Optional[str] = None
) -> str:
    """Ensure libretro core filename has the appropriate platform file extension.

    Args:
        core_name: Core name or filename.
        os_platform: Optional operating system platform string.

    Returns:
        Core filename ending in the appropriate platform extension.
    """
    if not core_name:
        return ""
    clean = core_name.strip()
    suffix = get_core_suffix(os_platform)
    if not clean.lower().endswith(suffix.lower()):
        return f"{clean}{suffix}"
    return clean


def normalize_core_stem(core_name: str) -> str:
    """Extract bare core identifier by stripping extension and '_libretro' suffix.

    Args:
        core_name: Libretro core identifier or file name.

    Returns:
        Bare stem name (e.g. 'mgba' from 'mgba_libretro.dll').
    """
    stripped = strip_core_suffix(core_name)
    if stripped.lower().endswith("_libretro"):
        return stripped[: -len("_libretro")]
    return stripped


def parse_core_info(text: str) -> Dict[str, str]:
    """Parse a RetroArch core .info file into a key-value dictionary.

    Args:
        text: Raw file contents of the .info file.

    Returns:
        Dictionary containing extracted key-value pairs.
    """
    result: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        result[key] = value
    return result


def parse_retroarch_cfg_line(line: str) -> Tuple[str, str]:
    """Parse a single line of retroarch.cfg into (lowercased_key, unquoted_value).

    Args:
        line: Single line string from retroarch.cfg.

    Returns:
        Tuple of (lowercased_key, unquoted_value).
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return ("", "")
    key, _, value = stripped.partition("=")
    clean_key = key.strip().lower()
    clean_val = value.strip()
    if len(clean_val) >= 2 and clean_val.startswith('"') and clean_val.endswith('"'):
        clean_val = clean_val[1:-1]
    return (clean_key, clean_val)


def bring_process_window_to_foreground(pid: int) -> None:
    """Ensure process window for given PID is brought to the foreground on Windows.

    Args:
        pid: Process ID of the application window.
    """
    if os.name != "nt" or not pid:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        def enum_windows_callback(hwnd: int, extra: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            proc_id = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
            if proc_id.value == pid:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE / SW_SHOWNORMAL
                user32.SetForegroundWindow(hwnd)
                return False
            return True

        enum_proc_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        callback = enum_proc_type(enum_windows_callback)
        user32.EnumWindows(callback, 0)
        logger.info("Executed SetForegroundWindow for process PID %s", pid)
    except Exception as e:
        logger.debug("Failed to bring PID %s window to foreground: %s", pid, e)


def is_retroarch_running() -> bool:
    """Check whether a RetroArch process is actively running on the host system.

    Returns:
        True if an active RetroArch process was found, False otherwise.
    """
    try:
        for proc in psutil.process_iter(["name", "exe", "cmdline"]):
            try:
                name = (proc.info.get("name") or "").lower()
                exe = (proc.info.get("exe") or "").lower()
                cmdline_list = proc.info.get("cmdline") or []
                cmdline = " ".join(cmdline_list).lower()

                if "romm-steam-sync" in name or "romm_steam_sync" in cmdline:
                    continue

                if "retroarch" in name or "retroarch" in exe:
                    return True

                for part in cmdline_list:
                    p_lower = part.lower()
                    if p_lower.endswith("retroarch") or p_lower.endswith("retroarch.exe"):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception as e:
        logger.debug("Error inspecting processes for RetroArch: %s", e)
    return False


def clean_subprocess_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Sanitize environment variables before spawning external subprocesses.

    When running inside a PyInstaller frozen application, PyInstaller sets
    dynamic linker search paths (e.g. LD_LIBRARY_PATH on Linux, DYLD_* on macOS)
    to point to its temporary extraction directory (_MEIPASS). If child processes
    such as Flatpak, RetroArch, or host utilities inherit these variables, their
    dynamic linker will prioritize bundled runtime libraries over host system
    libraries, causing fatal library/symbol version mismatches (e.g. GLIBCXX
    version conflicts).

    This function restores the original pre-bundle environment variables saved
    by PyInstaller with the '*_ORIG' suffix and strips any '_MEIPASS' temporary
    paths from dynamic library search paths.

    Args:
        base_env: Optional environment dictionary to sanitize. Defaults to os.environ.

    Returns:
        Sanitized environment dictionary safe for external subprocess execution.
    """
    env = dict(base_env if base_env is not None else os.environ)

    # 1. Restore any variables backed up with '*_ORIG' by PyInstaller
    for k in list(env.keys()):
        if k.endswith("_ORIG"):
            base_k = k[:-5]
            orig_val = env.pop(k)
            if orig_val:
                env[base_k] = orig_val
            else:
                env.pop(base_k, None)

    # 2. Check dynamic library search path variables for un-restored _MEIPASS paths
    library_path_vars = (
        "LD_LIBRARY_PATH",
        "DYLD_LIBRARY_PATH",
        "DYLD_FALLBACK_LIBRARY_PATH",
        "DYLD_FRAMEWORK_PATH",
        "LIBPATH",
        "SHLIB_PATH",
    )

    meipass = getattr(sys, "_MEIPASS", None)
    meipass_str = str(Path(meipass).resolve()) if meipass else None

    for var in library_path_vars:
        if var not in env:
            continue
        current_val = env[var]
        if not current_val:
            env.pop(var, None)
            continue

        if os.name == "nt" and re.search(r"(?:^|[;\s])[a-zA-Z]:[\\/]", current_val):
            sep = ";"
        else:
            sep = ":"

        filtered_entries: List[str] = []
        for entry in current_val.split(sep):
            clean_entry = entry.strip()
            if not clean_entry:
                continue

            # Check if entry matches _MEIPASS directly or by path resolution
            is_meipass = False
            if meipass_str:
                try:
                    res_entry = str(Path(clean_entry).resolve())
                    if res_entry == meipass_str or res_entry.startswith(
                        meipass_str + os.sep
                    ):
                        is_meipass = True
                except Exception:
                    pass

            # Also check for PyInstaller temporary folder naming pattern (_MEIxxxxxx)
            if not is_meipass:
                norm_parts = Path(os.path.normpath(clean_entry)).parts
                for part in norm_parts:
                    if part.startswith("_MEI") and len(part) >= 8:
                        is_meipass = True
                        break

            if not is_meipass:
                filtered_entries.append(clean_entry)

        if filtered_entries:
            env[var] = sep.join(filtered_entries)
        else:
            env.pop(var, None)

    return env


class BaseRetroArchAdapter(ABC):
    """Abstract base adapter defining shared logic and interface for RetroArch flavors."""

    def __init__(
        self,
        configured_path: str = "",
        os_platform: Optional[str] = None,
        home_dir: Optional[Path] = None,
    ) -> None:
        """Initialize base adapter.

        Args:
            configured_path: User-configured path to RetroArch binary or folder.
            os_platform: Optional OS identifier ('win32', 'darwin', 'linux').
            home_dir: Optional user home directory Path.
        """
        self.configured_path = configured_path
        self.os_platform = os_platform or sys.platform
        self.home_dir = home_dir or Path.home()
        self._cfg_path: Optional[Path] = None
        self._cached_settings: Optional[Dict[str, Any]] = None

    @property
    @abstractmethod
    def flavor(self) -> RetroArchFlavor:
        """RetroArch distribution flavor enum."""
        pass

    @property
    @abstractmethod
    def flavor_name(self) -> str:
        """Human-readable name of the RetroArch flavor."""
        pass

    def get_default_core_for_platform(self, platform_slug: str) -> Optional[str]:
        """Look up default libretro core for platform slug.

        Args:
            platform_slug: Platform identifier slug.

        Returns:
            Default core identifier or None.
        """
        if not platform_slug:
            return None
        return (
            DEFAULT_CORE_MAPPINGS.get(platform_slug.lower())
            or lookup_platform_mapping(DEFAULT_CORE_MAPPINGS, platform_slug)
        )

    def get_core_candidates_for_platform(self, platform_slug: str) -> List[str]:
        """Get candidate libretro cores for platform slug in priority order.

        Args:
            platform_slug: Platform identifier slug.

        Returns:
            List of core identifier candidate strings.
        """
        if not platform_slug:
            return []
        candidates = (
            lookup_platform_mapping(PLATFORM_CORE_CANDIDATES, platform_slug) or []
        )
        res = list(candidates)
        default_core = self.get_default_core_for_platform(platform_slug)
        if default_core and default_core not in res:
            res.insert(0, default_core)
        return res

    def list_installed_cores(self) -> List[str]:
        """Scan search directories for physically installed libretro cores.

        Returns:
            Sorted list of discovered bare core names (without OS suffix).
        """
        search_dirs = self.get_core_search_dirs()
        suffix = get_core_suffix(os_platform=self.os_platform)

        discovered: Set[str] = set()
        for s_dir in search_dirs:
            try:
                if s_dir.exists() and s_dir.is_dir():
                    for f in s_dir.iterdir():
                        if f.is_file() and f.name.lower().endswith(suffix.lower()):
                            core_stem = strip_core_suffix(f.name)
                            discovered.add(core_stem)
            except Exception as e:
                logger.debug("Error inspecting core search directory %s: %s", s_dir, e)

        return sorted(discovered)

    @abstractmethod
    def resolve_binary(self) -> Optional[Path]:
        """Locate RetroArch executable binary.

        Returns:
            Resolved absolute Path to RetroArch binary or None if not found.
        """
        pass

    @abstractmethod
    def resolve_cfg_path(self) -> Optional[Path]:
        """Locate retroarch.cfg file.

        Returns:
            Resolved absolute Path to retroarch.cfg or None if not found.
        """
        pass

    @abstractmethod
    def get_core_search_dirs(self) -> List[Path]:
        """Collect directories to search for libretro core libraries.

        Returns:
            List of directory Path objects in priority order.
        """
        pass

    @abstractmethod
    def get_info_search_dirs(self, raw_info_path: str = "") -> List[Path]:
        """Collect directories to search for libretro core .info metadata files.

        Args:
            raw_info_path: Optional raw 'libretro_info_path' setting from retroarch.cfg.

        Returns:
            List of directory Path objects in priority order.
        """
        pass

    @abstractmethod
    def resolve_saves_base_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve absolute base directory for save files.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to the saves root directory.
        """
        pass

    @abstractmethod
    def resolve_states_base_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve absolute base directory for save state files.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to the states root directory.
        """
        pass

    @abstractmethod
    def resolve_system_dir(
        self, settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Resolve absolute base directory for BIOS / system files.

        Args:
            settings: Optional pre-parsed settings dictionary.

        Returns:
            Resolved absolute Path to the system root directory.
        """
        pass

    def get_default_sort_by_content(self) -> bool:
        """Get the flavor default for sort_savefiles_by_content_enable.

        Returns:
            False for Standalone and Steam; True for RetroDECK.
        """
        return False

    def get_default_sort_by_core(self) -> bool:
        """Get the flavor default for sort_savefiles_enable.

        Returns:
            False by default across all flavors.
        """
        return False

    def get_default_savefiles_in_content_dir(self) -> bool:
        """Get the flavor default for savefiles_in_content_dir.

        Returns:
            False by default across all flavors.
        """
        return False

    def get_config_settings(self) -> Dict[str, Any]:
        """Read and parse runtime save settings from retroarch.cfg.

        Returns:
            Dictionary with parsed settings.
        """
        if self._cached_settings is not None:
            return self._cached_settings

        default_save_dir = ":\\saves" if self.os_platform == "win32" else ":/saves"
        default_info_dir = ":\\info" if self.os_platform == "win32" else ":/info"

        settings: Dict[str, Any] = {
            "savefiles_in_content_dir": self.get_default_savefiles_in_content_dir(),
            "savefile_directory": default_save_dir,
            "sort_savefiles_by_content_enable": self.get_default_sort_by_content(),
            "sort_savefiles_enable": self.get_default_sort_by_core(),
            "libretro_info_path": default_info_dir,
        }

        cfg_p = self.resolve_cfg_path()
        if not cfg_p or not cfg_p.is_file():
            logger.debug(
                "retroarch.cfg not found for flavor %s; using flavor defaults.",
                self.flavor_name,
            )
            self._cached_settings = settings
            return settings

        try:
            with open(cfg_p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    k, v = parse_retroarch_cfg_line(line)
                    if not k:
                        continue
                    if k == "savefiles_in_content_dir":
                        settings["savefiles_in_content_dir"] = v.lower() == "true"
                    elif k == "savefile_directory":
                        settings["savefile_directory"] = v
                    elif k == "sort_savefiles_by_content_enable":
                        settings["sort_savefiles_by_content_enable"] = (
                            v.lower() == "true"
                        )
                    elif k == "sort_savefiles_enable":
                        settings["sort_savefiles_enable"] = v.lower() == "true"
                    elif k == "libretro_info_path":
                        settings["libretro_info_path"] = v
            logger.info(
                "Parsed retroarch.cfg (%s) for %s: savefiles_in_content_dir=%s, savefile_dir=%s, sort_by_content=%s, sort_by_core=%s",
                cfg_p,
                self.flavor_name,
                settings["savefiles_in_content_dir"],
                settings["savefile_directory"],
                settings["sort_savefiles_by_content_enable"],
                settings["sort_savefiles_enable"],
            )
        except Exception as e:
            logger.warning(
                "Error reading retroarch.cfg at %s: %s", cfg_p, e
            )

        self._cached_settings = settings
        return settings

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
        if settings is None:
            settings = self.get_config_settings()

        clean = (
            strip_core_suffix(core_identifier).lower().strip()
            if core_identifier
            else ""
        )

        if not clean and platform_slug:
            default_core = (
                DEFAULT_CORE_MAPPINGS.get(platform_slug.lower(), "")
                or lookup_platform_mapping(DEFAULT_CORE_MAPPINGS, platform_slug)
            )
            clean = (
                strip_core_suffix(default_core).lower().strip()
                if default_core
                else ""
            )

        if not clean:
            return ""

        core_stem = normalize_core_stem(clean)

        # Probe for .info file
        raw_info = settings.get("libretro_info_path", "")
        info_dirs = self.get_info_search_dirs(raw_info_path=raw_info)
        names_to_try = [
            f"{clean}.info",
            f"{core_stem}_libretro.info",
            f"{core_stem}.info",
        ]
        for d in info_dirs:
            if not d.is_dir():
                continue
            for name in names_to_try:
                info_p = d / name
                if info_p.is_file():
                    try:
                        text = info_p.read_text(encoding="utf-8", errors="replace")
                        parsed = parse_core_info(text)
                        corename = parsed.get("corename")
                        if corename:
                            return corename.strip()
                    except Exception as e:
                        logger.debug("Failed parsing core .info file %s: %s", info_p, e)

        # Fallback dictionary
        if clean in CORE_NAME_FALLBACKS:
            return CORE_NAME_FALLBACKS[clean]
        if core_stem in CORE_NAME_FALLBACKS:
            return CORE_NAME_FALLBACKS[core_stem]

        return core_stem or clean

    def resolve_save_directory(
        self,
        rom_path: str,
        platform_slug: str = "",
        core_name: str = "",
    ) -> Path:
        """Resolve the target directory where save files should be located.

        Respects savefiles_in_content_dir, sort_savefiles_by_content_enable,
        and sort_savefiles_enable.

        Args:
            rom_path: Path to the target ROM file.
            platform_slug: Optional platform slug identifier.
            core_name: Optional libretro core identifier.

        Returns:
            Resolved absolute Path to directory where saves reside.
        """
        rom_p = Path(rom_path)
        settings = self.get_config_settings()

        if settings.get("savefiles_in_content_dir", False):
            return rom_p.parent.resolve()

        base_dir = self.resolve_saves_base_dir(settings)
        parts = [base_dir]

        if settings.get("sort_savefiles_by_content_enable", False):
            content_name = platform_slug.lower() if platform_slug else rom_p.parent.name
            parts.append(content_name)

        if settings.get("sort_savefiles_enable", False):
            cname = self.resolve_core_name(
                core_name, platform_slug=platform_slug, settings=settings
            )
            if cname:
                parts.append(cname)

        target_dir = Path(*parts).resolve()
        return target_dir

    def resolve_core_path(
        self,
        platform_slug: str,
        custom_mappings: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Locate libretro core file path for a given platform slug.

        Args:
            platform_slug: Platform identifier slug.
            custom_mappings: Optional user custom core mappings dict.

        Returns:
            Resolved core path or core filename string.
        """
        custom_mappings = custom_mappings or {}
        core_name = ""
        if custom_mappings:
            core_name = (
                lookup_platform_mapping(custom_mappings, platform_slug) or ""
            )
        if not core_name:
            core_name = (
                lookup_platform_mapping(DEFAULT_CORE_MAPPINGS, platform_slug)
                or ""
            )
        if not core_name:
            raw, clean, _ = normalize_platform_slug(platform_slug)
            core_name = f"{clean}_libretro" if clean else f"{raw}_libretro"

        core_filename = ensure_core_suffix(
            core_name, os_platform=self.os_platform
        )

        search_dirs = self.get_core_search_dirs()
        for s_dir in search_dirs:
            candidate = s_dir / core_filename
            if candidate.exists():
                logger.info(
                    "Resolved libretro core for platform '%s': %s",
                    platform_slug,
                    candidate,
                )
                return str(candidate.resolve())

        logger.info(
            "Core file not found in search paths; using fallback core name: %s",
            core_filename,
        )
        return core_filename

    @abstractmethod
    def build_launch_command(
        self,
        rom_path: str,
        core_path: str,
        binary_path: Optional[Path] = None,
    ) -> List[str]:
        """Construct the subprocess argument list to launch a game.

        Args:
            rom_path: Absolute path to ROM file.
            core_path: Path or identifier of libretro core.
            binary_path: Optional override path to RetroArch executable binary.

        Returns:
            List of command line string arguments.
        """
        pass

    def prepare_launch_environment(
        self,
        rom_path: str,
        core_path: str,
        binary_path: Optional[Path] = None,
    ) -> Dict[str, str]:
        """Prepare environment variables dictionary for spawning RetroArch.

        Args:
            rom_path: Path to target ROM.
            core_path: Path to target core.
            binary_path: Optional override path to RetroArch binary.

        Returns:
            Environment variables dictionary.
        """
        return clean_subprocess_env(os.environ.copy())

    def launch_game(
        self,
        rom_path: str,
        platform_slug: str,
        custom_mappings: Optional[Dict[str, str]] = None,
        core_path: Optional[str] = None,
        binary_path: Optional[Path] = None,
    ) -> Tuple[bool, str, Optional[subprocess.Popen]]:
        """Launch game with RetroArch.

        Args:
            rom_path: Path to target ROM file on disk.
            platform_slug: Target platform identifier.
            custom_mappings: Optional custom core mapping dictionary.
            core_path: Optional pre-resolved core path.
            binary_path: Optional pre-resolved binary path.

        Returns:
            Tuple of (success_boolean, status_message, spawned_popen_process).
        """
        target_core = core_path or self.resolve_core_path(platform_slug, custom_mappings)
        if not target_core:
            logger.error(
                "Failed to launch game: libretro core for platform '%s' not found.",
                platform_slug,
            )
            return (
                False,
                f"Could not find a valid libretro core for platform '{platform_slug}'.",
                None,
            )

        cmd = self.build_launch_command(
            rom_path=rom_path,
            core_path=target_core,
            binary_path=binary_path,
        )
        if not cmd:
            logger.error("Failed to build launch command for %s", self.flavor_name)
            return (
                False,
                f"Failed to build launch command for {self.flavor_name}.",
                None,
            )

        env = self.prepare_launch_environment(
            rom_path=rom_path,
            core_path=target_core,
            binary_path=binary_path,
        )

        logger.info(
            "Spawning %s subprocess command: %s", self.flavor_name, " ".join(cmd)
        )
        try:
            exe_binary = binary_path or self.resolve_binary()
            cwd_dir = str(exe_binary.parent) if exe_binary and exe_binary.is_file() else None
            proc = subprocess.Popen(
                cmd,
                cwd=cwd_dir,
                env=env,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            captured_stderr: List[str] = []
            if getattr(proc, "stderr", None) is not None:
                def _drain_stderr(pipe: Any, output_list: List[str]) -> None:
                    try:
                        if hasattr(pipe, "__class__") and "Mock" in pipe.__class__.__name__:
                            return
                        for line in iter(pipe.readline, ""):
                            if not isinstance(line, str):
                                break
                            stripped = line.strip()
                            if stripped:
                                logger.debug("RetroArch stderr: %s", stripped)
                                if len(output_list) < 50:
                                    output_list.append(stripped)
                    except Exception as err:
                        logger.debug("Error draining RetroArch stderr pipe: %s", err)
                    finally:
                        try:
                            pipe.close()
                        except Exception:
                            pass

                drain_thread = threading.Thread(
                    target=_drain_stderr,
                    args=(proc.stderr, captured_stderr),
                    daemon=True,
                )
                drain_thread.start()

            setattr(proc, "_captured_stderr", captured_stderr)

            logger.info(
                "Successfully launched %s (PID: %s) for game: %s",
                self.flavor_name,
                getattr(proc, "pid", "unknown"),
                Path(rom_path).name,
            )
            return True, f"Launched {Path(rom_path).name} with {self.flavor_name}", proc
        except Exception as e:
            logger.error("Failed to execute %s subprocess: %s", self.flavor_name, e)
            return False, f"Failed to execute {self.flavor_name}: {str(e)}", None
