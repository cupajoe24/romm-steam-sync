"""Rom aggregate root representing a synced ROM."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Rom:
    """Rom aggregate entity representing game metadata and Steam bindings.

    Attributes:
        rom_id: Unique RomM identifier for this ROM.
        platform_slug: Target platform slug (e.g. 'ps1', 'snes').
        name: Clean display name of the game.
        shortcut_app_id: Signed or unsigned 32-bit Steam shortcut ID if bound.
        sibling_group_key: Coalesced key identifying sibling variants of the game.
        summary: Optional textual synopsis or game description.
        cover_url: Remote URL or path to game artwork/cover image.
        fs_name: Actual filename of the ROM on disk or server.
        sgdb_id: SteamGridDB game identifier if matched.
        igdb_id: IGDB game identifier if matched.
    """

    rom_id: int
    platform_slug: str
    name: str
    shortcut_app_id: Optional[int] = None
    sibling_group_key: Optional[str] = None
    summary: Optional[str] = None
    cover_url: Optional[str] = None
    fs_name: Optional[str] = None
    sgdb_id: Optional[int] = None
    igdb_id: Optional[int] = None

    @property
    def is_bound(self) -> bool:
        """Whether this Rom is bound to a Steam shortcut."""
        return self.shortcut_app_id is not None

    def bind_shortcut(self, app_id: int) -> None:
        """Bind non-Steam shortcut AppID to this Rom.

        Args:
            app_id: Steam non-Steam shortcut identifier (signed or unsigned 32-bit integer).
        """
        self.shortcut_app_id = app_id

    def unbind_shortcut(self) -> None:
        """Clear shortcut binding."""
        self.shortcut_app_id = None
