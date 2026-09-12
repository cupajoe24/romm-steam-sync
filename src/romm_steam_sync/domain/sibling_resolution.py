"""Deterministic sibling-group representative resolution and canonical naming.

A sibling group represents one game with several versions, dumps, or discs
(e.g., region and revision variants).

Provides:
1. resolve_group_representative: Selects which ROM version to bind to
   (installed > bound > default is_main_sibling > 1G1R rank).
2. canonical_group_name: Determines the clean Steam shortcut name.
"""

from __future__ import annotations

import functools
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from romm_steam_sync.domain.dict_helpers import extract_rom_id

DEFAULT_REGION_PRIORITY: Tuple[str, ...] = ("World", "USA", "Europe", "Japan")
_DEFAULT_REGION_INDEX: Dict[str, int] = {
    name.casefold(): i for i, name in enumerate(DEFAULT_REGION_PRIORITY)
}

AUTO_REGION = "auto"

_BUCKET_PREFERRED = 0
_BUCKET_DEFAULT = 1
_BUCKET_OTHER = 2
_BUCKET_NONE = 3

_PRERELEASE_MARKERS: Tuple[str, ...] = ("alpha", "beta", "proto", "sample", "demo")
_RANK_RETAIL = 0
_RANK_PRERELEASE = 1

_DIGIT_RUN = re.compile(r"(\d+)")


def _single_region_rank(region: str, preferred_region: str) -> Tuple[int, int, str]:
    """Calculate the bucket and rank index for a single region string.

    Args:
        region: Name of region to rank.
        preferred_region: User-configured preferred region or 'auto'.

    Returns:
        Tuple representing priority sort key.
    """
    folded = region.casefold()
    if preferred_region != AUTO_REGION and folded == preferred_region.casefold():
        return (_BUCKET_PREFERRED, 0, "")
    default_idx = _DEFAULT_REGION_INDEX.get(folded)
    if default_idx is not None:
        return (_BUCKET_DEFAULT, default_idx, "")
    return (_BUCKET_OTHER, 0, folded)


def _best_region_rank(
    member: Dict[str, Any], preferred_region: str
) -> Tuple[int, int, str]:
    """Calculate the best region rank among all regions assigned to a ROM member.

    Args:
        member: Dictionary of ROM metadata.
        preferred_region: Target region preference.

    Returns:
        Best (lowest) region rank tuple.
    """
    regions = member.get("regions") or []
    if not regions:
        # Also check name for region markers like (USA), (Europe), (Japan), (World)
        name = str(member.get("name") or "")
        detected = []
        for r_name in DEFAULT_REGION_PRIORITY:
            if f"({r_name})" in name or f"({r_name.lower()})" in name.lower():
                detected.append(r_name)
        if detected:
            regions = detected
    if not regions:
        return (_BUCKET_NONE, 0, "")
    return min(_single_region_rank(str(r), preferred_region) for r in regions)


def _is_prerelease_tag(tag: str) -> bool:
    """Check if a tag string indicates a pre-release build.

    Args:
        tag: Tag or flag string.

    Returns:
        True if tag indicates alpha, beta, proto, demo, or sample.
    """
    folded = tag.strip().casefold()
    for marker in _PRERELEASE_MARKERS:
        if folded == marker:
            return True
        if folded.startswith(marker):
            rest = folded[len(marker) :].lstrip()
            if rest and rest[0].isdigit():
                return True
    return False


def _prerelease_rank(member: Dict[str, Any]) -> int:
    """Determine pre-release ranking (0 for retail, 1 for prerelease).

    Args:
        member: ROM metadata dictionary.

    Returns:
        0 for retail releases, 1 for pre-release builds.
    """
    tags = member.get("tags") or []
    if any(_is_prerelease_tag(str(t)) for t in tags):
        return _RANK_PRERELEASE
    name = str(member.get("name") or "").casefold()
    for marker in _PRERELEASE_MARKERS:
        if f"({marker}" in name or f"[{marker}" in name:
            return _RANK_PRERELEASE
    return _RANK_RETAIL


def _natural_sort_key(text: str) -> Tuple[Tuple[int, int, str], ...]:
    """Compute natural numerical sort key for strings containing digits.

    Args:
        text: Input string.

    Returns:
        Tuple suitable for natural alphanumeric sorting.
    """
    key: List[Tuple[int, int, str]] = []
    for part in _DIGIT_RUN.split(text.casefold()):
        if not part:
            continue
        if part.isdecimal():
            key.append((1, int(part), ""))
        else:
            key.append((0, 0, part))
    return tuple(key)


@functools.total_ordering
class _RevisionKey:
    """Sort key ordering revisions newest-first (min picks the highest)."""

    __slots__ = ("_key",)

    def __init__(self, revision: str) -> None:
        """Initialize revision sort key.

        Args:
            revision: Revision string (e.g. 'v1.01', 'Rev A').
        """
        self._key = _natural_sort_key(revision)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _RevisionKey):
            return NotImplemented
        return self._key == other._key

    def __lt__(self, other: _RevisionKey) -> bool:
        return self._key > other._key

    def __hash__(self) -> int:
        return hash(self._key)


def _rank_key(
    member: Dict[str, Any], preferred_region: str = AUTO_REGION
) -> Tuple[int, Tuple[int, int, str], _RevisionKey, str, int]:
    """Total pure order over a group's members.

    Order: prerelease > region > revision > fs_name > rom_id.

    Args:
        member: ROM metadata dictionary.
        preferred_region: User preferred region or 'auto'.

    Returns:
        Sort key tuple.
    """
    rom_id_val = extract_rom_id(member)
    fs_name_val = str(
        member.get("fs_name")
        or member.get("fs_name_no_ext")
        or member.get("name")
        or ""
    ).lower()
    rev_val = str(member.get("revision") or "")
    if not rev_val:
        # Extract (Rev X) or (v1.X) from name
        m = re.search(r"\((Rev \d+|v\d+(\.\d+)?)\)", str(member.get("name") or ""))
        if m:
            rev_val = m.group(1)

    return (
        _prerelease_rank(member),
        _best_region_rank(member, preferred_region),
        _RevisionKey(rev_val),
        fs_name_val,
        rom_id_val,
    )


def resolve_group_representative(
    members: List[Dict[str, Any]],
    installed_rom_ids: Optional[Set[int]] = None,
    bound_rom_ids: Optional[Set[int]] = None,
    preferred_region: str = AUTO_REGION,
) -> int:
    """Return the representative rom_id for a sibling group's members.

    Resolution chain:
    1. Installed sibling on local disk
    2. Sibling with an existing shortcut binding
    3. RomM default (is_main_sibling)
    4. 1G1R rank (prerelease demotion > region priority > revision > alphabetical > rom_id)

    Args:
        members: List of ROM dictionaries in the sibling group.
        installed_rom_ids: Optional set of rom_ids installed on local disk.
        bound_rom_ids: Optional set of rom_ids currently bound to Steam shortcuts.
        preferred_region: User-configured region priority string.

    Returns:
        The winning representative rom_id.

    Raises:
        ValueError: If members list is empty.
    """
    if not members:
        raise ValueError("Cannot resolve representative for empty members list")

    inst_set = installed_rom_ids or set()
    bound_set = bound_rom_ids or set()

    for leg in (
        [m for m in members if extract_rom_id(m) in inst_set],
        [m for m in members if extract_rom_id(m) in bound_set],
        [m for m in members if m.get("is_main_sibling")],
        members,
    ):
        if leg:
            winner = min(leg, key=lambda m: _rank_key(m, preferred_region))
            return extract_rom_id(winner)

    winner = members[0]
    return extract_rom_id(winner)



def canonical_group_name(
    members: List[Dict[str, Any]], preferred_region: str = AUTO_REGION
) -> str:
    """Derive the clean canonical game name from the best-ranked sibling version.

    Args:
        members: List of ROM member dictionaries in the sibling group.
        preferred_region: User preferred region string.

    Returns:
        Canonical game name string.

    Raises:
        ValueError: If members list is empty.
    """
    if not members:
        raise ValueError("Cannot derive canonical name for empty members list")

    winner = min(members, key=lambda m: _rank_key(m, preferred_region))
    return str(winner.get("name") or "")
