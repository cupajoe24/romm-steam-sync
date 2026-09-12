"""RomInstall aggregate root recording local installation state."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class RomInstall:
    """Aggregate entity tracking downloaded and installed ROM files on disk.

    Attributes:
        rom_id: RomM identifier of the installed ROM.
        file_path: Absolute path to the primary launchable ROM file.
        rom_dir: Optional directory containing multi-file extracted ROM assets.
        launchable: Whether the installation is directly launchable.
        installed_at: UTC timestamp when the installation completed.
    """

    rom_id: int
    file_path: str
    rom_dir: Optional[str] = None
    launchable: bool = True
    installed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Initialize default installation timestamp if omitted."""
        if self.installed_at is None:
            self.installed_at = datetime.now(timezone.utc)
