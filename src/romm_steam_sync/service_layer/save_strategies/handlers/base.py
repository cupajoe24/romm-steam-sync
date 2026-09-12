"""Abstract base class for platform- and core-specific memory card handlers."""

from abc import ABC, abstractmethod
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Sanitize string for use in save file names across operating systems.

    Args:
        name: Raw filename string to sanitize.

    Returns:
        Sanitized filename string with forbidden characters removed.
    """
    if not name:
        return ""
    # Strip invalid filesystem characters (\ / : * ? " < > |)
    sanitized = re.sub(r'[\\/*?:"<>|]', "", name)
    # Collapse multiple whitespaces/underscores
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized


class BaseMemoryCardHandler(ABC):
    """Abstract interface for platform/core-specific memory card location and naming logic."""

    @abstractmethod
    def extract_rom_metadata(self, rom_path: str) -> Dict[str, Any]:
        """Extract metadata (GameID, Title, Region, etc.) from ROM if readable.

        Args:
            rom_path: Path to the ROM file.

        Returns:
            Dictionary containing extracted metadata fields.
        """

    @abstractmethod
    def get_save_directories(
        self,
        configured_retroarch_path: str = "",
        rom_path: str = "",
        platform_slug: str = "",
    ) -> List[Path]:
        """Resolve candidate save directories where the core expects memory cards.

        Args:
            configured_retroarch_path: Configured path to RetroArch binary.
            rom_path: Path to ROM.
            platform_slug: Platform identifier slug.

        Returns:
            List of candidate save directories.
        """

    @abstractmethod
    def resolve_target_save_path(
        self,
        save_dirs: List[Path],
        rom_path: str,
        remote_filename: str = "",
        remote_ext: str = "",
        platform_slug: str = "",
    ) -> Path:
        """Determine default target path to place/download the save file.

        Args:
            save_dirs: Candidate directories.
            rom_path: Path to ROM.
            remote_filename: Optional remote filename.
            remote_ext: Optional remote extension.
            platform_slug: Platform slug.

        Returns:
            Resolved destination Path object.
        """

    @abstractmethod
    def find_existing_save(
        self,
        save_dirs: List[Path],
        rom_path: str,
        remote_filename: str = "",
        remote_ext: str = "",
        platform_slug: str = "",
    ) -> Optional[Path]:
        """Search save directories for existing game memory card file.

        Args:
            save_dirs: Candidate directories.
            rom_path: Path to ROM.
            remote_filename: Optional remote filename.
            remote_ext: Optional remote extension.
            platform_slug: Platform slug.

        Returns:
            Path to existing save file if found, or None.
        """
