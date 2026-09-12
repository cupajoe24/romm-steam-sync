"""Sibling-group key derivation via connected components over RomM sibling edges.

Two RomM ROMs represent the same game (siblings) when they share any non-null
external metadata ID across eight sources (IGDB, ScreenScraper, Moby, RA,
Hasheous, LaunchBox, TGDB, Flashpoint), scoped per platform, or when RomM
explicitly links them via sibling_roms edges. The client mirrors that relation
by building connected components over each fetch's sibling_roms edges and
keying a whole component by its canonical source — the highest-priority source
whose value the component agrees on.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from romm_steam_sync.domain.dict_helpers import extract_platform_id, extract_rom_id

# (RomM dict field, key-source label) in RomM's coalesce order
_META_ID_SOURCES: Tuple[Tuple[str, str], ...] = (
    ("igdb_id", "igdb"),
    ("ss_id", "ss"),
    ("moby_id", "moby"),
    ("ra_id", "ra"),
    ("hasheous_id", "hasheous"),
    ("launchbox_id", "launchbox"),
    ("tgdb_id", "tgdb"),
    ("flashpoint_id", "flashpoint"),
)

# Reverse lookup source-label -> RomM dict field
_FIELD_BY_SOURCE: Dict[str, str] = {
    source: field for field, source in _META_ID_SOURCES
}


def compute_sibling_group_key(rom: Dict[str, Any]) -> str:
    """Return the per-platform coalesce-first sibling-group key for a rom dict.

    Coalesces the external-metadata ids in _META_ID_SOURCES order and formats
    "{source}:{id}:{platform_id}" (e.g. "igdb:3404:57"). When the ROM matched no
    service, falls back to "romm:{rom_id}:{platform_id}" — its own id, a solo group.

    Args:
        rom: Dictionary representation of a ROM from RomM API.

    Returns:
        Formatted sibling group key string.
    """
    platform_id = extract_platform_id(rom)

    # Check top-level and nested metadata
    metadata = rom.get("metadata") if isinstance(rom.get("metadata"), dict) else {}

    for field, source in _META_ID_SOURCES:
        value = rom.get(field) or metadata.get(field)
        if value is not None:
            return f"{source}:{value}:{platform_id}"

    # Also check sgdb_id as secondary
    sgdb = rom.get("sgdb_id") or metadata.get("sgdb_id")
    if sgdb is not None:
        return f"sgdb:{sgdb}:{platform_id}"

    rom_id = extract_rom_id(rom)
    return f"romm:{rom_id}:{platform_id}"



def _parse_group_key(key: str) -> Optional[Tuple[str, str]]:
    """Split a "{source}:{value}:{platform}" key into (source, value).

    Args:
        key: Raw sibling group key string.

    Returns:
        Tuple of (source_label, id_value) or None if invalid.
    """
    if not key:
        return None
    parts = key.split(":")
    if len(parts) != 3:
        return None
    source, value, _platform = parts
    if source not in _FIELD_BY_SOURCE and source != "sgdb":
        return None
    return source, value


class _UnionFind:
    """Deterministic union-find whose component root is always the smallest id."""

    def __init__(self, ids: Set[int]) -> None:
        """Initialize union-find disjoint sets with a set of integer IDs.

        Args:
            ids: Set of integer member IDs.
        """
        self._parent: Dict[int, int] = {i: i for i in ids}

    def find(self, x: int) -> int:
        """Find the canonical root ID for item x with path compression.

        Args:
            x: Member identifier.

        Returns:
            Representative root identifier for x's set.
        """
        root = x
        while self._parent.get(root, root) != root:
            root = self._parent[root]
        while self._parent.get(x, x) != root:
            parent = self._parent.get(x, x)
            self._parent[x] = root
            x = parent
        return root

    def union(self, a: int, b: int) -> None:
        """Merge sets containing elements a and b, preserving smaller ID as root.

        Args:
            a: First member identifier.
            b: Second member identifier.
        """
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        lo, hi = (ra, rb) if ra < rb else (rb, ra)
        self._parent[hi] = lo


def compute_component_group_keys(
    unit_roms: List[Dict[str, Any]],
    resident_keys: Optional[Mapping[int, str]] = None,
) -> Dict[int, str]:
    """Derive a sibling-group key for every fresh ROM in a fetched sync unit.

    Performs union-find over sibling_roms edges between members, coalescing
    external metadata ids across all members of each connected component.

    Args:
        unit_roms: List of raw ROM dictionaries fetched in the current sync unit.
        resident_keys: Optional mapping of existing local rom_id to group keys.

    Returns:
        Mapping of rom_id to canonical computed sibling group keys.
    """
    resident_lookup: Dict[int, str] = {
        int(k): v for k, v in (resident_keys or {}).items()
    }
    fresh_by_id: Dict[int, Dict[str, Any]] = {}
    in_unit_resident: Dict[int, str] = {}

    for rom in unit_roms:
        rom_id = extract_rom_id(rom)
        if rom_id <= 0:
            continue
        key = rom.get("sibling_group_key")
        if key:
            in_unit_resident[rom_id] = key
        else:
            fresh_by_id[rom_id] = rom

    resident_lookup.update(in_unit_resident)
    fresh_ids = set(fresh_by_id.keys())
    uf = _UnionFind(fresh_ids)
    resident_candidates: Dict[int, List[Tuple[str, str]]] = {}

    for rom_id in sorted(fresh_ids):
        siblings = fresh_by_id[rom_id].get("sibling_roms") or []
        for sibling in siblings:
            if isinstance(sibling, dict):
                target_id = extract_rom_id(sibling)
            elif isinstance(sibling, (int, str)) and str(sibling).isdigit():
                target_id = int(sibling)
            else:
                target_id = 0


            if target_id <= 0 or target_id == rom_id:
                continue
            if target_id in fresh_ids:
                uf.union(rom_id, target_id)
            elif target_id in resident_lookup:
                parsed = _parse_group_key(resident_lookup[target_id])
                if parsed is not None:
                    resident_candidates.setdefault(rom_id, []).append(parsed)

    components: Dict[int, List[int]] = {}
    for rom_id in sorted(fresh_ids):
        root = uf.find(rom_id)
        components.setdefault(root, []).append(rom_id)

    result: Dict[int, str] = {}
    for member_ids in components.values():
        values_by_source: Dict[str, Set[str]] = {}
        for member_id in member_ids:
            rom = fresh_by_id[member_id]
            metadata = (
                rom.get("metadata") if isinstance(rom.get("metadata"), dict) else {}
            )
            for field, source in _META_ID_SOURCES:
                value = rom.get(field) or metadata.get(field)
                if value is not None:
                    values_by_source.setdefault(source, set()).add(str(value))
            for source, value in resident_candidates.get(member_id, []):
                values_by_source.setdefault(source, set()).add(value)

        canonical = next(
            (
                source
                for _field, source in _META_ID_SOURCES
                if source in values_by_source
            ),
            None,
        )
        values = values_by_source.get(canonical) if canonical is not None else None

        if canonical is None or values is None or len(values) != 1:
            for member_id in member_ids:
                result[member_id] = compute_sibling_group_key(fresh_by_id[member_id])
        else:
            value = next(iter(values))
            for member_id in member_ids:
                rom = fresh_by_id[member_id]
                platform_id = extract_platform_id(rom)
                result[member_id] = f"{canonical}:{value}:{platform_id}"


    return result


def target_in_sibling_group(
    *,
    bound_group_key: Optional[str],
    target_group_key: Optional[str] = None,
    target_ids: Optional[Mapping[str, Any]] = None,
    target_is_local: bool = True,
    target_is_server_sibling: bool = False,
) -> bool:
    """Check whether a target ROM belongs to the bound ROM's sibling group.

    Args:
        bound_group_key: Sibling group key of the bound shortcut ROM.
        target_group_key: Sibling group key of the target candidate ROM.
        target_ids: External metadata ID mapping for candidate ROM.
        target_is_local: Whether target ROM is present locally.
        target_is_server_sibling: Whether target ROM is linked as sibling on server.

    Returns:
        True if target ROM is verified as belonging to the sibling group.
    """
    if not (target_is_local or target_is_server_sibling):
        return False
    if bound_group_key is None:
        return True
    if target_is_local:
        return target_group_key == bound_group_key
    parsed = _parse_group_key(bound_group_key)
    if parsed is None or target_ids is None:
        return False
    source, value = parsed
    field_name = _FIELD_BY_SOURCE.get(source)
    if not field_name:
        return False
    target_value = target_ids.get(field_name)
    return target_value is None or str(target_value) == value
