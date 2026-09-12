"""Disc-based platform classification, archive format identification, and launch file resolution."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from typing import List, Optional, Set, Union

from romm_steam_sync.domain.platform import (
    DISC_PLATFORM_ALIASES as _DISC_PLATFORM_ALIASES,
    DISC_PLATFORM_SLUGS,
    lookup_platform_mapping,
)

logger = logging.getLogger(__name__)

# Canonical platform identifiers for disc-based systems
DISC_BASED_PLATFORMS: frozenset[str] = DISC_PLATFORM_SLUGS

# Comprehensive aliases mapping to canonical disc-based platforms
DISC_PLATFORM_ALIASES: dict[str, str] = dict(_DISC_PLATFORM_ALIASES)

# Recognized archive extensions
ARCHIVE_EXTENSIONS: frozenset[str] = frozenset({
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".tgz",
    ".bz2",
    ".tbz2",
    ".xz",
    ".txz",
})

# Compound archive suffixes (e.g. .tar.gz)
COMPOUND_ARCHIVE_SUFFIXES: tuple[str, ...] = (
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tar.zst",
)

# Recognized launchable disc-image extensions
DISC_IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".cue",
    ".chd",
    ".iso",
    ".rvz",
    ".gdi",
    ".cdi",
    ".wbfs",
    ".pbp",
    ".ciso",
    ".gcz",
    ".m3u",
    ".toc",
    ".nrg",
    ".mdf",
    ".wud",
    ".wux",
    ".wua",
    ".rpx",
    ".elf",
    ".dol",
})

# Extension priority for launch file resolution
LAUNCH_EXTENSION_PRIORITY: list[str] = [
    ".m3u",
    ".cue",
    ".gdi",
    ".toc",
    ".chd",
    ".iso",
    ".rvz",
    ".wbfs",
    ".pbp",
    ".cdi",
    ".ciso",
    ".gcz",
    ".wud",
    ".wux",
    ".wua",
    ".rpx",
    ".elf",
    ".dol",
    ".nrg",
    ".mdf",
    ".img",
    ".bin",
]

# Ignored non-game extensions and filenames
IGNORED_EXTENSIONS: frozenset[str] = frozenset({
    ".txt",
    ".nfo",
    ".url",
    ".xml",
    ".json",
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".ico",
    ".md",
    ".pdf",
    ".doc",
    ".docx",
    ".sfv",
    ".diz",
    ".srm",
    ".sav",
    ".state",
})


def can_play_archives(platform_slug: Optional[str]) -> bool:
    """Return True if the platform can execute compressed archives without extraction.

    Args:
        platform_slug: Platform slug or identifier string.

    Returns:
        True if the platform can play compressed archives, False if extraction is required.
    """
    if not platform_slug:
        return True
    if lookup_platform_mapping(DISC_PLATFORM_ALIASES, platform_slug) is not None:
        return False
    return lookup_platform_mapping({s: s for s in DISC_BASED_PLATFORMS}, platform_slug) is None


def is_disc_based_platform(platform_slug: Optional[str]) -> bool:
    """Return True if platform is an optical disc-based system requiring uncompressed ROMs.

    Args:
        platform_slug: Platform slug or identifier string.

    Returns:
        True if the platform is recognized as disc-based, False otherwise.
    """
    return not can_play_archives(platform_slug)



def is_archive_file(path_or_filename: Union[str, Path]) -> bool:
    """Return True if the file name/path has an archive or compressed extension.

    Args:
        path_or_filename: File path or filename string/Path.

    Returns:
        True if the extension corresponds to an archive format.
    """
    name = Path(path_or_filename).name.lower()
    for compound in COMPOUND_ARCHIVE_SUFFIXES:
        if name.endswith(compound):
            return True
    suffix = Path(path_or_filename).suffix.lower()
    return suffix in ARCHIVE_EXTENSIONS


def should_extract_rom(
    platform_slug: Optional[str], path_or_filename: Union[str, Path]
) -> bool:
    """Decide whether a downloaded ROM should be extracted based on platform and format.

    Args:
        platform_slug: Platform slug or identifier.
        path_or_filename: Downloaded ROM path or filename.

    Returns:
        True if the ROM needs extraction prior to launch.
    """
    return not can_play_archives(platform_slug) and is_archive_file(path_or_filename)


def detect_launch_file(
    extracted_files: List[Union[str, Path]],
    preferred_stem: Optional[str] = None,
) -> Optional[Path]:
    """Pick the primary launchable ROM file from a list of extracted files.

    Priority hierarchy:
    1. Preferred stem match with .m3u > .cue > .gdi > .chd > .iso > .rvz > .wbfs > .pbp > .cdi > others
    2. Any .m3u playlist
    3. Any .cue sheet
    4. Any .gdi sheet
    5. Any .chd, .iso, .rvz, .wbfs, .pbp, .cdi, .ciso, .gcz
    6. Largest file by size

    Args:
        extracted_files: List of extracted paths or filename strings.
        preferred_stem: Optional filename stem to prioritize during matching.

    Returns:
        Path to the best launch target file, or None if no valid file found.
    """
    if not extracted_files:
        return None

    paths = [Path(p) for p in extracted_files]
    # Filter out directory entries, hidden files, and non-game metadata
    valid_files = [
        p for p in paths
        if not p.is_dir()
        and not p.name.startswith(".")
        and not p.name.startswith("._")
        and "__MACOSX" not in p.parts
        and p.suffix.lower() not in IGNORED_EXTENSIONS
    ]

    if not valid_files:
        # If all were filtered out, fall back to any non-dir file
        valid_files = [p for p in paths if not p.is_dir()]
        if not valid_files:
            return paths[0] if paths else None

    if len(valid_files) == 1:
        return valid_files[0]

    pref_lower = preferred_stem.strip().lower() if preferred_stem else None

    def ext_priority(path: Path) -> int:
        """Calculate priority rank index for a file extension."""
        s = path.suffix.lower()
        if s in LAUNCH_EXTENSION_PRIORITY:
            return LAUNCH_EXTENSION_PRIORITY.index(s)
        return len(LAUNCH_EXTENSION_PRIORITY) + 1

    # 1. If preferred_stem given, check for exact/stem match among prioritized extensions
    if pref_lower:
        stem_matches = [p for p in valid_files if p.stem.lower() == pref_lower]
        if stem_matches:
            stem_matches.sort(key=lambda p: (ext_priority(p), -_safe_file_size(p)))
            return stem_matches[0]

    # 2. Check prioritized extensions across all valid files
    for target_ext in LAUNCH_EXTENSION_PRIORITY:
        ext_matches = [p for p in valid_files if p.suffix.lower() == target_ext]
        if ext_matches:
            if pref_lower:
                for match in ext_matches:
                    if pref_lower in match.stem.lower():
                        return match
            # Pick largest file if multiple matches for same extension
            ext_matches.sort(key=lambda p: -_safe_file_size(p))
            return ext_matches[0]

    # 3. Fallback: largest valid file by size
    valid_files.sort(key=lambda p: -_safe_file_size(p))
    return valid_files[0]


def _strip_file_extension(path_or_name: str) -> str:
    """Extract base filename without trailing archive or disc image extension.

    Args:
        path_or_name: File path or name.

    Returns:
        Stripped base name string.
    """
    name = Path(path_or_name).name
    # Strip compound archive suffixes (.tar.gz, .tar.bz2, etc.)
    for compound in COMPOUND_ARCHIVE_SUFFIXES:
        if name.lower().endswith(compound):
            return name[:-len(compound)]
    # Strip standard file extension if present (e.g. .iso, .chd, .zip, .7z, .cue)
    return re.sub(r"\.[a-zA-Z0-9]{1,7}$", "", name)


def extract_disc_identifier(
    title_or_path: Optional[Union[str, Path]]
) -> Optional[str]:
    """Extract normalized disc/disc-variant identifier from title or filename.

    Args:
        title_or_path: ROM title or path string/Path.

    Returns:
        Normalized identifier string (e.g. 'disc 1', 'side a', 'leon disc') or None.

    Examples:
        'Devil May Cry 2 (USA) (Disc 1)' -> 'disc 1'
        'Devil May Cry 2 (USA) (Disc 2)' -> 'disc 2'
        'Final Fantasy VII (USA) (Disc 1 of 3)' -> 'disc 1'
        'Resident Evil 2 (USA) (Leon Disc)' -> 'leon disc'
        'Game (Disk 2)' -> 'disc 2'
        'Game (CD 1)' -> 'disc 1'
        'Game (Side A)' -> 'side a'
        'Game_Disc2.iso' -> 'disc 2'
        'Super Mario World' -> None
    """
    if not title_or_path:
        return None
    name = _strip_file_extension(str(title_or_path))

    # 1. Standard numbered/lettered disc/disk/cd (e.g. Disc 1, Disk 2, CD 1, Disc A, Disc 1 of 3)
    m = re.search(
        r"(?:\(|\b|_|-)(?:disc|disk|cd)\s*([0-9]+|[a-z])(?:\s+of\s+[0-9]+)?(?:\)|\b|_|-)",
        name,
        re.IGNORECASE,
    )
    if m:
        return f"disc {m.group(1).lower()}"

    # 2. Side / Part / Pt
    m = re.search(
        r"(?:\(|\b|_|-)(?:side|part|pt)\s*([0-9]+|[a-z])(?:\)|\b|_|-)",
        name,
        re.IGNORECASE,
    )
    if m:
        prefix = "side" if "side" in m.group(0).lower() else "part"
        return f"{prefix} {m.group(1).lower()}"

    # 3. Named special discs in parentheses e.g. (Leon Disc), (Claire Disc), (Bonus Disc), (Install Disc)
    m = re.search(r"\(([^)]*(?:disc|disk|cd)[^)]*)\)", name, re.IGNORECASE)
    if m:
        cleaned = re.sub(r"\s+", " ", m.group(1).strip().lower())
        return cleaned

    return None


def extract_revision_identifier(
    title_or_path: Optional[Union[str, Path]]
) -> Optional[str]:
    """Extract normalized revision/version identifier from title or filename.

    Args:
        title_or_path: ROM title or path string/Path.

    Returns:
        Normalized revision string (e.g. 'rev 1', 'v1.01') or None.

    Examples:
        'Game (USA) (v1.01)' -> 'v1.01'
        'Game (USA) (Rev 1)' -> 'rev 1'
        'Game (USA) (Rev A)' -> 'rev a'
        'Game (USA)' -> None
    """
    if not title_or_path:
        return None
    name = _strip_file_extension(str(title_or_path))

    m = re.search(
        r"(?:\(|\b)(?:rev|revision)\.?\s*([0-9]+|[a-z])(?:\)|\b)",
        name,
        re.IGNORECASE,
    )
    if m:
        return f"rev {m.group(1).lower()}"

    m = re.search(r"(?:\(|\b)(v[0-9]+(?:\.[0-9]+)?)(?:\)|\b)", name, re.IGNORECASE)
    if m:
        return m.group(1).lower()

    return None


def sanitize_title(title: Optional[str]) -> str:
    """Strip region/version brackets and non-alphanumeric characters for clean game matching.

    Args:
        title: Raw game title string.

    Returns:
        Sanitized lowercase alphanumeric string.
    """
    if not title:
        return ""
    s = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", title)
    s = re.sub(r"[^a-zA-Z0-9\s]", "", s).strip().lower()
    return s


def titles_match(rom_title: str, file_stem: str) -> bool:
    """Check if a Rom database title matches a local file stem accurately.

    Prevents false-positive sequel or disc matching.

    Args:
        rom_title: Game title from RomM metadata.
        file_stem: Filename stem of local file.

    Returns:
        True if the titles match the same game release.
    """
    # 1. Disc identifier check: if both have disc indicators and they differ, do not match
    disc1 = extract_disc_identifier(rom_title)
    disc2 = extract_disc_identifier(file_stem)
    if disc1 and disc2 and disc1 != disc2:
        return False

    # 2. Revision identifier check: if both have revisions and they differ, do not match
    rev1 = extract_revision_identifier(rom_title)
    rev2 = extract_revision_identifier(file_stem)
    if rev1 and rev2 and rev1 != rev2:
        return False

    st1 = sanitize_title(rom_title)
    st2 = sanitize_title(file_stem)
    if not st1 or not st2:
        return False
    if st1 == st2:
        return True

    s1_ns = re.sub(r"\s+", "", st1)
    s2_ns = re.sub(r"\s+", "", st2)
    if s1_ns == s2_ns:
        return True

    d1 = re.findall(r"\d+", st1)
    d2 = re.findall(r"\d+", st2)
    if d1 != d2:
        return False
    words1 = set(st1.split())
    words2 = set(st2.split())
    if words1 and words2 and (words1.issubset(words2) or words2.issubset(words1)):
        return True
    return False


def _safe_file_size(path: Path) -> int:
    """Return file size in bytes safely, returning 0 if missing or inaccessible.

    Args:
        path: Path object to inspect.

    Returns:
        File size in bytes, or 0 if inaccessible.
    """
    try:
        if path.exists() and path.is_file():
            return path.stat().st_size
    except (OSError, ValueError) as e:
        logger.debug("Could not determine file size for %s: %s", path, e)
    return 0
