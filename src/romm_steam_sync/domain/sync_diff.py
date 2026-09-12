"""Library synchronization difference calculation domain models."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from romm_steam_sync.domain.rom import Rom


@dataclass
class PlatformSyncDiff:
    """Sync difference model for a single emulation platform.

    Attributes:
        platform_slug: Platform identifier (e.g. 'ps1', 'snes').
        platform_name: Human-readable platform display name.
        additions: List of newly discovered ROM dictionaries to add.
        removals_roms: List of Rom entities no longer present on server.
        removals_shortcuts: List of orphan Steam shortcut dictionaries to prune.
        unchanged_roms: List of unchanged ROM dictionaries.
    """

    platform_slug: str
    platform_name: str
    additions: List[Dict[str, Any]] = field(default_factory=list)
    removals_roms: List[Rom] = field(default_factory=list)
    removals_shortcuts: List[Dict[str, Any]] = field(default_factory=list)
    unchanged_roms: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def additions_count(self) -> int:
        """Count of new items to add."""
        return len(self.additions)

    @property
    def removals_count(self) -> int:
        """Count of ROMs and shortcuts to remove."""
        return len(self.removals_roms) + len(self.removals_shortcuts)

    @property
    def unchanged_count(self) -> int:
        """Count of unchanged existing ROMs."""
        return len(self.unchanged_roms)


@dataclass
class SyncDiff:
    """Library-wide synchronization diff aggregated across all platforms.

    Attributes:
        platform_diffs: Mapping of platform slugs to their respective PlatformSyncDiff.
    """

    platform_diffs: Dict[str, PlatformSyncDiff] = field(default_factory=dict)

    @property
    def total_additions(self) -> int:
        """Total count of additions across all platforms."""
        return sum(pd.additions_count for pd in self.platform_diffs.values())

    @property
    def total_removals(self) -> int:
        """Total count of removals across all platforms."""
        return sum(pd.removals_count for pd in self.platform_diffs.values())

    @property
    def total_unchanged(self) -> int:
        """Total count of unchanged ROMs across all platforms."""
        return sum(pd.unchanged_count for pd in self.platform_diffs.values())
