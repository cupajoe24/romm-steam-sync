"""RetroArch adapters package providing support for Steam, Standalone, and RetroDECK.

Exports base abstractions, flavor-specific adapters, and detection factories.
"""

from romm_steam_sync.adapters.retroarch.base import (
    CORE_NAME_FALLBACKS,
    DEFAULT_CORE_MAPPINGS,
    PLATFORM_CORE_CANDIDATES,
    BaseRetroArchAdapter,
    bring_process_window_to_foreground,
    clean_subprocess_env,
    ensure_core_suffix,
    get_core_suffix,
    is_retroarch_running,
    lookup_platform_mapping,
    normalize_core_stem,
    normalize_platform_slug,
    parse_core_info,
    parse_retroarch_cfg_line,
    strip_core_suffix,
)
from romm_steam_sync.adapters.retroarch.detector import (
    RetroArchFlavor,
    detect_retroarch_flavor,
    get_retroarch_adapter,
)
from romm_steam_sync.adapters.retroarch.retrodeck import (
    RetroDeckAdapter,
    RetroDeckConfigHealth,
)
from romm_steam_sync.adapters.retroarch.standalone import (
    StandaloneRetroArchAdapter,
)
from romm_steam_sync.adapters.retroarch.steam import (
    SteamRetroArchAdapter,
)

__all__ = [
    "BaseRetroArchAdapter",
    "SteamRetroArchAdapter",
    "StandaloneRetroArchAdapter",
    "RetroDeckAdapter",
    "RetroDeckConfigHealth",
    "RetroArchFlavor",
    "detect_retroarch_flavor",
    "get_retroarch_adapter",
    "bring_process_window_to_foreground",
    "clean_subprocess_env",
    "is_retroarch_running",
    "get_core_suffix",
    "strip_core_suffix",
    "ensure_core_suffix",
    "normalize_core_stem",
    "normalize_platform_slug",
    "lookup_platform_mapping",
    "parse_core_info",
    "parse_retroarch_cfg_line",
    "DEFAULT_CORE_MAPPINGS",
    "PLATFORM_CORE_CANDIDATES",
    "CORE_NAME_FALLBACKS",
]
