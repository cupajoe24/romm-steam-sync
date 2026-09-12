"""Display and string formatting helpers for the RomM launcher."""

from pathlib import Path
from typing import Any, Dict, Tuple


def format_size(size_bytes: int) -> str:
    """Format byte count into human-readable size string.

    Args:
        size_bytes: Number of bytes to format.

    Returns:
        Formatted human-readable string (e.g. '14 MB', '2.00 GB').
    """
    if size_bytes <= 0:
        return "Unknown size"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.0f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_version_display(v: Dict[str, Any], canonical_name: str) -> Tuple[str, str]:
    """Derive a distinguishing title and metadata summary string for a ROM version.

    Args:
        v: ROM version dictionary containing metadata fields.
        canonical_name: Fallback canonical name for the ROM.

    Returns:
        Tuple of (title, subtitle) strings for display.
    """
    v_id = v.get("id") or 0
    raw_name = v.get("name") or f"ROM #{v_id}"
    fs_name = v.get("fs_name") or v.get("file_name") or ""
    fs_name_no_ext = v.get("fs_name_no_ext") or (Path(fs_name).stem if fs_name else "")
    if not fs_name_no_ext and v.get("file_path"):
        fs_name_no_ext = Path(v["file_path"]).stem

    # 1. Determine Title
    title = fs_name_no_ext if fs_name_no_ext else raw_name
    if not title or title.lower() == "none":
        title = raw_name

    # 2. Build Subtitle Metadata Badges
    meta_parts: list[str] = []

    # Regions
    regions = v.get("regions") or []
    if not regions and v.get("region"):
        regions = [v["region"]]
    if regions:
        if isinstance(regions, list):
            meta_parts.append(f"Region: {', '.join(str(r) for r in regions)}")
        else:
            meta_parts.append(f"Region: {regions}")

    # Revision / Version / Disc
    revision = v.get("revision") or v.get("version")
    if revision:
        meta_parts.append(f"Version: {revision}")
    if v.get("disc"):
        meta_parts.append(f"Disc: {v.get('disc')}")

    # Languages
    languages = v.get("languages") or []
    if languages:
        if isinstance(languages, list):
            lang_str = ", ".join(str(l) for l in languages[:4])
            meta_parts.append(f"Languages: {lang_str}")
        else:
            meta_parts.append(f"Languages: {languages}")

    # File Size
    size_bytes = v.get("file_size") or v.get("fs_size_bytes") or 0
    if size_bytes > 0:
        meta_parts.append(f"Size: {format_size(size_bytes)}")
    elif fs_name:
        meta_parts.append(f"File: {Path(fs_name).name}")

    if not meta_parts:
        if fs_name:
            meta_parts.append(f"File: {Path(fs_name).name}")
        else:
            meta_parts.append(f"ROM ID: #{v_id}")

    subtitle = "  •  ".join(meta_parts)
    return title, subtitle
