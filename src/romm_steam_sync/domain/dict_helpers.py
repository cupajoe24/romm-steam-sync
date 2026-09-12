"""Helper functions for safely extracting identifiers and metadata from ROM dictionaries."""

from typing import Any, Dict


def extract_rom_id(rom: Dict[str, Any]) -> int:
    """Extract integer rom_id from a raw ROM dictionary.

    Args:
        rom: Dictionary representation of a ROM or sibling group member.

    Returns:
        Integer ROM ID, or 0 if missing or unparseable.
    """
    if not isinstance(rom, dict):
        return 0
    val = rom.get("id")
    if val is None or val == "":
        val = rom.get("rom_id")
    if val is None or val == "":
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def extract_platform_id(rom: Dict[str, Any]) -> Any:
    """Extract platform identifier or slug from a raw ROM dictionary.

    Args:
        rom: Dictionary representation of a ROM.

    Returns:
        Platform identifier, slug, or 'default' fallback.
    """
    if not isinstance(rom, dict):
        return "default"
    platform_id = rom.get("platform_id") or rom.get("platform_slug") or "default"
    platform = rom.get("platform")
    if isinstance(platform, dict):
        platform_id = (
            platform.get("id")
            or platform.get("slug")
            or platform_id
        )
    return platform_id
