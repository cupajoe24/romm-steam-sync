"""RetroArch flavor detection and factory functions.

Provides automatic environment sniffing and explicit factory instantiation for
Steam RetroArch, Standalone RetroArch, and RetroDECK adapters.
"""

from enum import Enum
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Optional, Union

from romm_steam_sync.adapters.retroarch.base import (
    BaseRetroArchAdapter,
    RetroArchFlavor,
)
from romm_steam_sync.adapters.retroarch.retrodeck import RetroDeckAdapter
from romm_steam_sync.adapters.retroarch.standalone import StandaloneRetroArchAdapter
from romm_steam_sync.adapters.retroarch.steam import SteamRetroArchAdapter

logger = logging.getLogger(__name__)


def detect_retroarch_flavor(
    configured_path: str = "",
    preferred_flavor: Optional[Union[str, RetroArchFlavor]] = None,
    os_platform: Optional[str] = None,
    home_dir: Optional[Path] = None,
    flavor: Optional[Union[str, RetroArchFlavor]] = None,
) -> BaseRetroArchAdapter:
    """Detect or instantiate the appropriate RetroArch flavor adapter.

    Evaluates explicit preference, user-configured path strings, and host
    filesystem environment to choose the optimal adapter.

    Args:
        configured_path: Optional user-configured path to RetroArch binary or folder.
        preferred_flavor: Optional explicit flavor setting ('auto', 'steam', 'standalone', 'retrodeck').
        os_platform: Optional operating system identifier string.
        home_dir: Optional user home directory Path.
        flavor: Alias for preferred_flavor.

    Returns:
        Instance of BaseRetroArchAdapter subclass tailored to target flavor.
    """
    plat = os_platform or sys.platform
    home = home_dir or Path.home()

    # 1. Respect explicit preference if not 'auto'
    active_pref = flavor if flavor is not None else preferred_flavor
    pref_str = (
        active_pref.value
        if isinstance(active_pref, RetroArchFlavor)
        else (active_pref or "").lower().strip()
    )

    if pref_str == RetroArchFlavor.STEAM.value:
        logger.debug("Using explicitly preferred flavor: Steam")
        return SteamRetroArchAdapter(
            configured_path=configured_path, os_platform=plat, home_dir=home
        )
    elif pref_str == RetroArchFlavor.STANDALONE.value:
        logger.debug("Using explicitly preferred flavor: Standalone")
        return StandaloneRetroArchAdapter(
            configured_path=configured_path, os_platform=plat, home_dir=home
        )
    elif pref_str == RetroArchFlavor.RETRODECK.value:
        logger.debug("Using explicitly preferred flavor: RetroDECK")
        return RetroDeckAdapter(
            configured_path=configured_path, os_platform=plat, home_dir=home
        )

    # 2. Inspect configured path hints
    if configured_path:
        clean_path = configured_path.replace("\\", "/").lower()
        if "net.retrodeck.retrodeck" in clean_path or "retrodeck" in clean_path:
            logger.info(
                "Detected RetroDECK from configured path: %s", configured_path
            )
            return RetroDeckAdapter(
                configured_path=configured_path, os_platform=plat, home_dir=home
            )
        if "steamapps" in clean_path or "/steam/" in clean_path or "\\steam\\" in configured_path.lower():
            logger.info(
                "Detected Steam RetroArch from configured path: %s", configured_path
            )
            return SteamRetroArchAdapter(
                configured_path=configured_path, os_platform=plat, home_dir=home
            )

    # 3. Check system PATH for standalone binaries (matches standard RetroArch precedence)
    which_ra = shutil.which("retroarch")
    if which_ra:
        try:
            if Path(which_ra).is_file():
                logger.info("Detected standalone RetroArch binary on system PATH: %s", which_ra)
                return StandaloneRetroArchAdapter(
                    configured_path=configured_path, os_platform=plat, home_dir=home
                )
        except Exception:
            pass

    which_flatpak_ra = shutil.which("org.libretro.RetroArch")
    if which_flatpak_ra:
        try:
            if Path(which_flatpak_ra).is_file():
                logger.info("Detected standalone Flatpak RetroArch binary on system PATH: %s", which_flatpak_ra)
                return StandaloneRetroArchAdapter(
                    configured_path=configured_path, os_platform=plat, home_dir=home
                )
        except Exception:
            pass

    # 4. Check for RetroDECK presence on Linux
    if plat.startswith("linux"):
        rd_json_str = os.path.join(
            str(home),
            ".var",
            "app",
            RetroDeckAdapter.FLATPAK_APP_ID,
            "config",
            "retrodeck",
            "retrodeck.json",
        )
        rd_app_dir = os.path.join(
            str(home), ".var", "app", RetroDeckAdapter.FLATPAK_APP_ID
        )
        if os.path.isfile(rd_json_str) or os.path.isdir(rd_app_dir):
            logger.info("Detected active RetroDECK Flatpak environment on system.")
            return RetroDeckAdapter(
                configured_path=configured_path, os_platform=plat, home_dir=home
            )

    # 5. Check for Standalone RetroArch in platform default paths
    standalone_adapter = StandaloneRetroArchAdapter(
        configured_path=configured_path, os_platform=plat, home_dir=home
    )
    if standalone_adapter.resolve_binary() is not None:
        logger.info("Detected active Standalone RetroArch installation.")
        return standalone_adapter

    # 6. Check for Steam RetroArch install
    steam_adapter = SteamRetroArchAdapter(
        configured_path=configured_path, os_platform=plat, home_dir=home
    )
    if steam_adapter.resolve_binary() is not None:
        logger.info("Detected active Steam RetroArch installation.")
        return steam_adapter

    # 7. Default fallback: Standalone
    logger.debug(
        "No explicit flavor matched; defaulting to Standalone RetroArch adapter."
    )
    return standalone_adapter


def get_retroarch_adapter(
    configured_path: str = "",
    preferred_flavor: Optional[Union[str, RetroArchFlavor]] = None,
    os_platform: Optional[str] = None,
    home_dir: Optional[Path] = None,
    flavor: Optional[Union[str, RetroArchFlavor]] = None,
) -> BaseRetroArchAdapter:
    """Convenience alias for detect_retroarch_flavor.

    Args:
        configured_path: Optional configured RetroArch path.
        preferred_flavor: Optional preferred flavor.
        os_platform: Optional OS identifier.
        home_dir: Optional home directory.
        flavor: Alias for preferred_flavor.

    Returns:
        BaseRetroArchAdapter subclass instance.
    """
    return detect_retroarch_flavor(
        configured_path=configured_path,
        preferred_flavor=preferred_flavor,
        os_platform=os_platform,
        home_dir=home_dir,
        flavor=flavor,
    )
