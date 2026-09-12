"""Steam user profile and installation path resolver across platforms."""

import logging
from pathlib import Path
import re
import sys
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class SteamPathResolver:
    """Discovers Steam installation root and user profile directories across platforms."""

    @classmethod
    def get_steam_root(cls) -> Optional[Path]:
        """Detect Steam installation root directory.

        Returns:
            Path to Steam installation folder, or None if not located.
        """
        if sys.platform == "win32":
            # Try Windows Registry
            try:
                import winreg

                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"
                )
                steam_path_str, _ = winreg.QueryValueEx(key, "SteamPath")
                winreg.CloseKey(key)
                p = Path(steam_path_str)
                if p.exists():
                    return p
            except Exception as e:
                logger.debug(
                    "Windows registry check for SteamPath encountered exception: %s",
                    e,
                )

            # Default Windows location
            default_win = Path("C:/Program Files (x86)/Steam")
            if default_win.exists():
                return default_win

        elif sys.platform == "darwin":
            mac_path = Path.home() / "Library" / "Application Support" / "Steam"
            if mac_path.exists():
                return mac_path

        else:
            # Linux candidate paths to search in priority order:
            # 1. Native standard XDG (~/.local/share/Steam) - Fedora RPM Fusion / standard
            # 2. ~/.steam/steam and ~/.steam/root (Standard Valve symlinks across Debian, Fedora, Arch)
            # 3. ~/.steam/debian-installation (Debian native APT package)
            # 4. Linux Flatpak (~/.var/app/com.valvesoftware.Steam/data/Steam)
            # 5. Linux Snap (~/snap/steam/common/.local/share/Steam) - Ubuntu Snap
            linux_candidates = [
                Path.home() / ".local" / "share" / "Steam",
                Path.home() / ".steam" / "steam",
                Path.home() / ".steam" / "debian-installation",
                Path.home() / ".steam" / "root",
                (
                    Path.home()
                    / ".var"
                    / "app"
                    / "com.valvesoftware.Steam"
                    / "data"
                    / "Steam"
                ),
                (
                    Path.home()
                    / "snap"
                    / "steam"
                    / "common"
                    / ".local"
                    / "share"
                    / "Steam"
                ),
                Path.home() / "snap" / "steam" / "common" / ".steam" / "steam",
            ]
            for cand in linux_candidates:
                if cand.exists():
                    return cand.resolve() if cand.is_symlink() else cand

        return None

    @classmethod
    def get_user_data_dir(cls, custom_steam_path: str = "") -> Optional[Path]:
        """Return base Steam userdata folder.

        Args:
            custom_steam_path: Optional user-configured custom Steam path.

        Returns:
            Path to Steam userdata folder or None if not found.
        """
        if custom_steam_path:
            p = Path(custom_steam_path)
            if (p / "userdata").exists():
                return p / "userdata"
            if p.name == "userdata":
                return p

        root = cls.get_steam_root()
        if root and (root / "userdata").exists():
            return root / "userdata"

        return None

    @classmethod
    def list_user_ids(cls, custom_steam_path: str = "") -> List[str]:
        """List active Steam profile user IDs in the userdata directory.

        Args:
            custom_steam_path: Optional custom Steam directory path.

        Returns:
            List of detected numeric user profile IDs.
        """
        userdata = cls.get_user_data_dir(custom_steam_path)
        if not userdata or not userdata.exists():
            return []

        user_ids = []
        for child in userdata.iterdir():
            if child.is_dir() and child.name.isdigit() and child.name != "0":
                user_ids.append(child.name)

        return user_ids

    @classmethod
    def get_user_config_dir(
        cls,
        user_id: str = "auto",
        custom_steam_path: str = "",
    ) -> Tuple[Optional[Path], str]:
        """Get Steam config directory for a specific user ID.

        If user_id is 'auto' or empty, picks the first available user profile ID.

        Args:
            user_id: Specific Steam user ID, or 'auto' for first available.
            custom_steam_path: Optional custom Steam directory.

        Returns:
            Tuple of (config_dir_path, selected_user_id).
        """
        user_ids = cls.list_user_ids(custom_steam_path)
        if not user_ids:
            return None, ""

        selected_id = user_id
        if user_id not in user_ids or user_id in ("auto", ""):
            selected_id = user_ids[0]

        userdata = cls.get_user_data_dir(custom_steam_path)
        if userdata:
            config_dir = userdata / selected_id / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            return config_dir, selected_id

        return None, ""

    @classmethod
    def get_library_folders(cls, custom_steam_path: str = "") -> List[Path]:
        """Detect all Steam library folders by inspecting libraryfolders.vdf.

        Args:
            custom_steam_path: Optional user-configured custom Steam path.

        Returns:
            List of Path objects pointing to detected Steam library directories.
        """
        folders: List[Path] = []
        seen: set[str] = set()

        root = cls.get_steam_root()
        if custom_steam_path:
            p = Path(custom_steam_path)
            if p.exists():
                root = p

        if root and root.exists():
            resolved = root.resolve()
            folders.append(resolved)
            seen.add(str(resolved).lower())

            vdf_path = root / "steamapps" / "libraryfolders.vdf"
            if vdf_path.is_file():
                try:
                    content = vdf_path.read_text(encoding="utf-8", errors="replace")
                    matches = re.findall(r'"path"\s+"([^"]+)"', content, re.IGNORECASE)
                    for match in matches:
                        clean_path = match.replace(r"\\", "\\")
                        lib_p = Path(clean_path)
                        if lib_p.exists():
                            res_lib = lib_p.resolve()
                            lib_key = str(res_lib).lower()
                            if lib_key not in seen:
                                seen.add(lib_key)
                                folders.append(res_lib)
                except Exception as e:
                    logger.warning(
                        "Error reading Steam library folders from %s: %s", vdf_path, e
                    )

        return folders
