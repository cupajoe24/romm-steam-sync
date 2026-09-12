"""Steam Process Guard to prevent writing shortcuts.vdf while Steam is active."""

import logging
from typing import List, Set

import psutil

logger = logging.getLogger(__name__)


class SteamGuard:
    """Inspects running system processes to ensure Steam is completely closed before writing."""

    STEAM_PROCESS_NAMES: Set[str] = {
        "steam.exe",
        "steam",
        "steam_osx",
        "steam.sh",
        "steamwebhelper.exe",
        "steamwebhelper",
    }

    @classmethod
    def is_steam_running(cls) -> bool:
        """Check if any Steam process is active.

        Returns:
            True if any Steam process is currently active, False otherwise.
        """
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name")
                if name and name.lower() in cls.STEAM_PROCESS_NAMES:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    @classmethod
    def get_running_steam_processes(cls) -> List[str]:
        """Return list of running Steam process names.

        Returns:
            List of detected active Steam process names.
        """
        running: List[str] = []
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info.get("name")
                if name and name.lower() in cls.STEAM_PROCESS_NAMES:
                    running.append(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return running
