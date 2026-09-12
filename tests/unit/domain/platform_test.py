"""Unit tests for domain platform registry and normalization utilities."""

import pytest

from romm_steam_sync.domain.platform import (
    DISC_PLATFORM_ALIASES,
    DISC_PLATFORM_SLUGS,
    PLATFORM_ALIASES,
    PLATFORM_DEFINITIONS,
    get_platform_aliases,
    lookup_platform_mapping,
    normalize_platform_identifier,
    normalize_platform_slug,
    strip_core_suffix,
)


def test_normalize_platform_slug_variants():
    """Verify platform slug normalization returns expected tuples."""
    assert normalize_platform_slug("") == ("", "", "")
    assert normalize_platform_slug("PlayStation 2") == (
        "playstation 2",
        "playstation-2",
        "playstation2",
    )
    assert normalize_platform_slug("super_nintendo") == (
        "super_nintendo",
        "super-nintendo",
        "supernintendo",
    )
    assert normalize_platform_slug("sega:cd") == (
        "sega:cd",
        "segacd",
        "segacd",
    )
    assert normalize_platform_slug("sega cd") == (
        "sega cd",
        "sega-cd",
        "segacd",
    )


def test_lookup_platform_mapping():
    """Verify looking up dictionary values across normalized slug variants."""
    mapping = {
        "ps1": "PlayStation 1",
        "playstation-2": "PS2 Target",
        "gamecube": "Dolphin GC",
    }
    assert lookup_platform_mapping(mapping, "") is None
    assert lookup_platform_mapping({}, "ps1") is None
    assert lookup_platform_mapping(mapping, "PS1") == "PlayStation 1"
    assert lookup_platform_mapping(mapping, "PlayStation 2") == "PS2 Target"
    assert lookup_platform_mapping(mapping, "game-cube") == "Dolphin GC"
    assert lookup_platform_mapping(mapping, "unknown_system") is None


def test_strip_core_suffix():
    """Verify dynamic library extensions are stripped safely."""
    assert strip_core_suffix("") == ""
    assert strip_core_suffix("snes9x_libretro.dll") == "snes9x_libretro"
    assert strip_core_suffix("pcsx2_libretro.so") == "pcsx2_libretro"
    assert strip_core_suffix("flycast_libretro.dylib") == "flycast_libretro"
    assert strip_core_suffix("genesis_plus_gx") == "genesis_plus_gx"


def test_platform_definitions_and_aliases():
    """Verify platform registry maps aliases and disc systems consistently."""
    assert len(PLATFORM_DEFINITIONS) >= 20
    assert "ps1" in DISC_PLATFORM_SLUGS
    assert "snes" not in DISC_PLATFORM_SLUGS

    # Check can_play_archives property on platform definitions
    ps1_defn = next(d for d in PLATFORM_DEFINITIONS if d.canonical_slug == "ps1")
    snes_defn = next(d for d in PLATFORM_DEFINITIONS if d.canonical_slug == "snes")
    assert ps1_defn.can_play_archives is False
    assert snes_defn.can_play_archives is True

    # Test derived aliases
    assert PLATFORM_ALIASES["psx"] == ("ps1", "PlayStation")
    assert PLATFORM_ALIASES["sfc"] == ("snes", "Super Nintendo")
    assert DISC_PLATFORM_ALIASES["psx"] == "ps1"
    assert "sfc" not in DISC_PLATFORM_ALIASES


def test_normalize_platform_identifier():
    """Verify normalizing raw input slugs to canonical pairs."""
    slug, display = normalize_platform_identifier("playstation 2")
    assert slug == "ps2"
    assert display == "PlayStation 2"

    slug, display = normalize_platform_identifier("CustomSystem")
    assert slug == "customsystem"
    assert display == "CustomSystem"


def test_get_platform_aliases():
    """Verify platform alias expansion includes keys and display names."""
    aliases = get_platform_aliases("ps1")
    assert "ps1" in aliases
    assert "psx" in aliases
    assert "playstation" in aliases
    assert "PlayStation" in aliases
