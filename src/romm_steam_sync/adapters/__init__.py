"""Infrastructure adapters for RomM API, Steam VDF, Steam Path, and Process Guard."""

from romm_steam_sync.adapters.archive_extractor import (
    ArchiveExtractor,
    ArchiveExtractorError,
    ZipSlipSecurityError,
)
from romm_steam_sync.adapters.retroarch_config import RetroArchConfigAdapter
from romm_steam_sync.adapters.retroarch_launcher import (
    RetroArchLauncher,
    clean_subprocess_env,
)
from romm_steam_sync.adapters.retroarch_paths import RetroArchPathResolver
from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.adapters.steam_backup import SteamBackupManager
from romm_steam_sync.adapters.steam_guard import SteamGuard
from romm_steam_sync.adapters.steam_localconfig import SteamLocalConfigManager
from romm_steam_sync.adapters.steam_path import SteamPathResolver
from romm_steam_sync.adapters.steam_vdf import SteamVdfManager, generate_app_id
from romm_steam_sync.adapters.steamgriddb import (
    SteamGridDbClient,
    SteamGridDbError,
)
from romm_steam_sync.adapters.wrapper_installer import (
    get_installed_wrapper_path,
    install_wrapper,
)

__all__ = [
    "ArchiveExtractor",
    "ArchiveExtractorError",
    "RetroArchConfigAdapter",
    "RetroArchLauncher",
    "RetroArchPathResolver",
    "RomMApiClient",
    "SteamBackupManager",
    "SteamGridDbClient",
    "SteamGridDbError",
    "SteamGuard",
    "SteamLocalConfigManager",
    "SteamPathResolver",
    "SteamVdfManager",
    "ZipSlipSecurityError",
    "clean_subprocess_env",
    "generate_app_id",
    "get_installed_wrapper_path",
    "install_wrapper",
]

