"""Canonical platform definitions, alias registries, and slug normalization utilities."""

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple


@dataclass(frozen=True)
class PlatformDefinition:
    """Definition of an emulated gaming platform.

    Attributes:
        canonical_slug: Standard lowercase slug key (e.g. 'ps1', 'gc').
        display_name: Formatted human-readable display title (e.g. 'PlayStation').
        aliases: List of alternate names, acronyms, and slugs for lookup.
        can_play_archives: Whether compressed archives (.zip/.7z) can be executed directly without extraction.
    """

    canonical_slug: str
    display_name: str
    aliases: Tuple[str, ...] = field(default_factory=tuple)
    can_play_archives: bool = True


# Canonical registry of supported platforms
PLATFORM_DEFINITIONS: Tuple[PlatformDefinition, ...] = (
    # Sony
    PlatformDefinition(
        canonical_slug="ps1",
        display_name="PlayStation",
        aliases=(
            "ps",
            "psx",
            "ps1",
            "playstation",
            "playstation-1",
            "playstation 1",
            "sony-playstation",
            "sony playstation",
        ),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="ps2",
        display_name="PlayStation 2",
        aliases=(
            "ps2",
            "playstation2",
            "playstation-2",
            "playstation 2",
            "sony-playstation-2",
            "sony playstation 2",
        ),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="ps3",
        display_name="PlayStation 3",
        aliases=(
            "ps3",
            "playstation3",
            "playstation-3",
            "playstation 3",
            "sony-playstation-3",
            "sony playstation 3",
        ),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="psp",
        display_name="PlayStation Portable",
        aliases=(
            "psp",
            "playstation-portable",
            "playstation portable",
            "sony-playstation-portable",
            "sony playstation portable",
        ),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="psvita",
        display_name="PlayStation Vita",
        aliases=(
            "psvita",
            "vita",
            "playstation-vita",
            "playstation vita",
            "sony-playstation-vita",
            "sony playstation vita",
        ),
        can_play_archives=False,
    ),
    # Nintendo
    PlatformDefinition(
        canonical_slug="gc",
        display_name="GameCube",
        aliases=(
            "gc",
            "ngc",
            "gamecube",
            "game-cube",
            "game cube",
            "nintendo-gamecube",
            "nintendo gamecube",
            "nintendo-game-cube",
            "nintendo game cube",
            "nintendo-gc",
            "nintendo gc",
            "nintendo-ngc",
            "nintendo ngc",
        ),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="wii",
        display_name="Wii",
        aliases=("wii", "nintendo-wii", "nintendo wii"),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="wiiu",
        display_name="Wii U",
        aliases=(
            "wiiu",
            "wii-u",
            "wii u",
            "nintendo-wii-u",
            "nintendo wii u",
        ),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="switch",
        display_name="Nintendo Switch",
        aliases=("switch", "nintendo-switch", "nintendo switch"),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="snes",
        display_name="Super Nintendo",
        aliases=(
            "snes",
            "super-nintendo",
            "super nintendo",
            "super-nintendo-entertainment-system",
            "super nintendo entertainment system",
            "sfc",
            "super-famicom",
            "super famicom",
        ),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="nes",
        display_name="Nintendo Entertainment System",
        aliases=(
            "nes",
            "nintendo-entertainment-system",
            "nintendo entertainment system",
            "famicom",
            "fc",
        ),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="n64",
        display_name="Nintendo 64",
        aliases=("n64", "nintendo-64", "nintendo 64"),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="gb",
        display_name="Game Boy",
        aliases=(
            "gb",
            "game-boy",
            "game boy",
            "nintendo-game-boy",
            "nintendo game boy",
        ),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="gbc",
        display_name="Game Boy Color",
        aliases=(
            "gbc",
            "game-boy-color",
            "game boy color",
            "nintendo-game-boy-color",
            "nintendo game boy color",
        ),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="gba",
        display_name="Game Boy Advance",
        aliases=(
            "gba",
            "game-boy-advance",
            "game boy advance",
            "nintendo-game-boy-advance",
            "nintendo game boy advance",
        ),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="nds",
        display_name="Nintendo DS",
        aliases=("nds", "ds", "nintendo-ds", "nintendo ds"),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="3ds",
        display_name="Nintendo 3DS",
        aliases=(
            "3ds",
            "n3ds",
            "nintendo-3ds",
            "nintendo 3ds",
            "new-nintendo-3ds",
            "new nintendo 3ds",
        ),
        can_play_archives=True,
    ),
    # Sega
    PlatformDefinition(
        canonical_slug="genesis",
        display_name="Sega Genesis",
        aliases=(
            "megadrive",
            "mega-drive",
            "mega drive",
            "genesis",
            "sega-genesis",
            "sega genesis",
            "sega-mega-drive",
            "sega mega drive",
            "sega-mega-drive--genesis",
        ),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="dreamcast",
        display_name="Dreamcast",
        aliases=("dc", "dreamcast", "sega-dreamcast", "sega dreamcast"),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="saturn",
        display_name="Sega Saturn",
        aliases=("saturn", "sega-saturn", "sega saturn"),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="mastersystem",
        display_name="Sega Master System",
        aliases=(
            "mastersystem",
            "master-system",
            "master system",
            "sega-master-system",
            "sega master system",
            "sms",
        ),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="gamegear",
        display_name="Sega Game Gear",
        aliases=(
            "gamegear",
            "game-gear",
            "game gear",
            "sega-game-gear",
            "sega game gear",
            "gg",
        ),
        can_play_archives=True,
    ),
    PlatformDefinition(
        canonical_slug="segacd",
        display_name="Sega CD",
        aliases=(
            "segacd",
            "sega-cd",
            "sega cd",
            "megacd",
            "mega-cd",
            "mega cd",
        ),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="sega32x",
        display_name="Sega 32X",
        aliases=("sega32x", "sega-32x", "sega 32x", "32x"),
        can_play_archives=True,
    ),
    # Others & Disc Systems
    PlatformDefinition(
        canonical_slug="3do",
        display_name="3DO Interactive Multiplayer",
        aliases=("3do", "panasonic-3do", "panasonic 3do"),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="pcecd",
        display_name="PC Engine CD-ROM²",
        aliases=(
            "pcecd",
            "pcenginecd",
            "pcengine-cd",
            "pc engine cd",
            "turbografxcd",
            "turbografx-cd",
            "turbografx 16 cd",
        ),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="neogeocd",
        display_name="Neo Geo CD",
        aliases=("neogeocd", "neo-geo-cd", "neo geo cd"),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="xbox",
        display_name="Xbox",
        aliases=("xbox", "original-xbox", "original xbox"),
        can_play_archives=False,
    ),
    PlatformDefinition(
        canonical_slug="xbox360",
        display_name="Xbox 360",
        aliases=("xbox360", "xbox-360", "xbox 360"),
        can_play_archives=False,
    ),
)


# Derived mapping: alias -> (canonical_slug, display_name)
PLATFORM_ALIASES: Dict[str, Tuple[str, str]] = {}

# Derived mapping: alias -> canonical_slug (platforms requiring archive extraction)
EXTRACT_REQUIRED_PLATFORM_ALIASES: Dict[str, str] = {}

# Derived set of canonical extract-required slugs
_extract_slugs_list: List[str] = []

for _defn in PLATFORM_DEFINITIONS:
    if not _defn.can_play_archives:
        _extract_slugs_list.append(_defn.canonical_slug)
    for _alias in _defn.aliases:
        PLATFORM_ALIASES[_alias] = (_defn.canonical_slug, _defn.display_name)
        if not _defn.can_play_archives:
            EXTRACT_REQUIRED_PLATFORM_ALIASES[_alias] = _defn.canonical_slug

EXTRACT_REQUIRED_PLATFORM_SLUGS: FrozenSet[str] = frozenset(_extract_slugs_list)

# Backward-compatibility aliases for optical disc systems requiring extraction
DISC_PLATFORM_ALIASES: Dict[str, str] = EXTRACT_REQUIRED_PLATFORM_ALIASES
DISC_PLATFORM_SLUGS: FrozenSet[str] = EXTRACT_REQUIRED_PLATFORM_SLUGS


def normalize_platform_slug(platform_slug: str) -> Tuple[str, str, str]:
    """Normalize a platform slug into raw, hyphenated, and unhyphenated variants.

    Args:
        platform_slug: Raw platform identifier slug.

    Returns:
        Tuple containing (raw_lowered, clean_hyphenated, clean_no_hyphen).
    """
    if not platform_slug:
        return ("", "", "")
    raw = platform_slug.lower().strip()
    clean = raw.replace(" ", "-").replace(":", "").replace("_", "-")
    clean_no_hyphen = clean.replace("-", "")
    return (raw, clean, clean_no_hyphen)


def lookup_platform_mapping(
    mapping: Dict[str, Any], platform_slug: str
) -> Optional[Any]:
    """Look up a value in a mapping dictionary using normalized platform slug variants.

    Args:
        mapping: Dictionary mapping platform slug strings to values.
        platform_slug: Platform identifier slug to look up.

    Returns:
        Matched value from mapping, or None if no variant matches.
    """
    if not mapping or not platform_slug:
        return None
    raw, clean, clean_no_hyphen = normalize_platform_slug(platform_slug)
    return (
        mapping.get(raw)
        or mapping.get(clean)
        or mapping.get(clean_no_hyphen)
    )


def strip_core_suffix(core_name: str) -> str:
    """Strip dynamic library extension (.dll, .so, .dylib) from a core name.

    Args:
        core_name: Core name or filename with or without file extension.

    Returns:
        Core name without dynamic library file extension.
    """
    if not core_name:
        return ""
    clean = core_name.strip()
    for ext in [".dll", ".so", ".dylib"]:
        if clean.lower().endswith(ext):
            return clean[: -len(ext)]
    return clean


def normalize_platform_identifier(raw: str) -> Tuple[str, str]:
    """Normalize any platform slug or name to (canonical_key, display_name).

    Args:
        raw: Raw platform slug or name string.

    Returns:
        Tuple of (canonical_slug_key, display_name).
    """
    clean = raw.strip().lower().replace(" ", "-").replace(":", "")
    clean_no_hyphen = clean.replace("-", "")

    if clean in PLATFORM_ALIASES:
        return PLATFORM_ALIASES[clean]
    if clean_no_hyphen in PLATFORM_ALIASES:
        return PLATFORM_ALIASES[clean_no_hyphen]

    display = raw.strip()
    if display.islower() and len(display) <= 4:
        display = display.upper()
    elif display.islower():
        display = display.title()
    return clean, display


def get_platform_aliases(canonical_key: str) -> List[str]:
    """Get all known slug and name aliases for a canonical platform key.

    Args:
        canonical_key: Canonical platform slug key.

    Returns:
        List of all associated alias strings.
    """
    aliases: Set[str] = {canonical_key}
    for alias, (ckey, dname) in PLATFORM_ALIASES.items():
        if ckey == canonical_key:
            aliases.add(alias)
            aliases.add(dname)
            aliases.add(dname.lower())
            aliases.add(dname.lower().replace(" ", "-"))
    return sorted(aliases)

