"""Domain model aggregate roots, value objects, and format classification."""

from romm_steam_sync.domain.disc_formats import (
    ARCHIVE_EXTENSIONS,
    DISC_BASED_PLATFORMS,
    DISC_IMAGE_EXTENSIONS,
    DISC_PLATFORM_ALIASES,
    can_play_archives,
    detect_launch_file,
    extract_disc_identifier,
    extract_revision_identifier,
    is_archive_file,
    is_disc_based_platform,
    sanitize_title,
    should_extract_rom,
    titles_match,
)
from romm_steam_sync.domain.dict_helpers import (
    extract_platform_id,
    extract_rom_id,
)
from romm_steam_sync.domain.kv_config import KvConfig
from romm_steam_sync.domain.platform import (
    PLATFORM_ALIASES,
    PLATFORM_DEFINITIONS,
    PlatformDefinition,
    get_platform_aliases,
    lookup_platform_mapping,
    normalize_platform_identifier,
    normalize_platform_slug,
    strip_core_suffix,
)
from romm_steam_sync.domain.playtime import PlaySession, RomPlaytime
from romm_steam_sync.domain.rom import Rom
from romm_steam_sync.domain.rom_install import RomInstall
from romm_steam_sync.domain.save_sync_state import FileSyncState, RomSaveSyncState
from romm_steam_sync.domain.sibling_group import (
    compute_component_group_keys,
    compute_sibling_group_key,
    target_in_sibling_group,
)
from romm_steam_sync.domain.sibling_resolution import (
    AUTO_REGION,
    DEFAULT_REGION_PRIORITY,
    canonical_group_name,
    resolve_group_representative,
)
from romm_steam_sync.domain.sync_diff import PlatformSyncDiff, SyncDiff
from romm_steam_sync.domain.sync_run import SyncRun

__all__ = [
    "ARCHIVE_EXTENSIONS",
    "AUTO_REGION",
    "DEFAULT_REGION_PRIORITY",
    "DISC_BASED_PLATFORMS",
    "DISC_IMAGE_EXTENSIONS",
    "DISC_PLATFORM_ALIASES",
    "FileSyncState",
    "KvConfig",
    "PLATFORM_ALIASES",
    "PLATFORM_DEFINITIONS",
    "PlatformDefinition",
    "PlatformSyncDiff",
    "PlaySession",
    "Rom",
    "RomInstall",
    "RomPlaytime",
    "RomSaveSyncState",
    "SyncDiff",
    "SyncRun",
    "can_play_archives",
    "canonical_group_name",
    "compute_component_group_keys",
    "compute_sibling_group_key",
    "detect_launch_file",
    "extract_disc_identifier",
    "extract_platform_id",
    "extract_revision_identifier",
    "extract_rom_id",
    "get_platform_aliases",
    "is_archive_file",
    "is_disc_based_platform",
    "lookup_platform_mapping",
    "normalize_platform_identifier",
    "normalize_platform_slug",
    "resolve_group_representative",
    "sanitize_title",
    "should_extract_rom",
    "strip_core_suffix",
    "target_in_sibling_group",
    "titles_match",
]

