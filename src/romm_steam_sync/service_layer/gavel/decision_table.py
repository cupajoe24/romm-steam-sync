"""Gavel decision table implementation.

Ported from romm-gavel (https://github.com/danielcopper/romm-gavel).
Copyright (c) 2026 danielcopper. Licensed under the MIT License.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional

from romm_steam_sync.service_layer.gavel.ladder import local_matches_server

logger = logging.getLogger(__name__)

SHRINK_RATIO = 0.5


def parse_iso_to_epoch(iso_str: Optional[str]) -> Optional[float]:
    """Parse ISO-8601 datetime string to Unix timestamp float (UTC).

    Args:
        iso_str: ISO-8601 formatted datetime string.

    Returns:
        Timestamp as float seconds since Unix epoch, or None.
    """
    if not iso_str:
        return None
    try:
        clean_str = (
            iso_str.replace("Z", "+00:00")
            if iso_str.endswith("Z")
            else iso_str
        )
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception as e:
        logger.debug("Failed parsing ISO timestamp '%s': %s", iso_str, e)
        return None


def is_implausibly_shrunken(
    new_size: Optional[int], baseline_size: Optional[int]
) -> bool:
    """Check whether a save file has shrunken below acceptable threshold.

    A 0-byte file is never a plausible edit; below half recorded size is a truncated write.

    Args:
        new_size: Current local save file size in bytes.
        baseline_size: Baseline save file size in bytes from previous sync.

    Returns:
        True if size reduction suggests corruption or truncation, False otherwise.
    """
    if new_size is None:
        return False
    if new_size == 0:
        return True
    if baseline_size is None or baseline_size <= 0:
        return False
    return new_size < baseline_size * SHRINK_RATIO


def compute_sync_action(
    local_exists: bool,
    local_hash: Optional[str],
    local_mtime: Optional[float],
    local_size: Optional[int],
    remote_save: Optional[Dict[str, Any]],
    last_sync_hash: Optional[str] = None,
    last_sync_server_hash: Optional[str] = None,
    last_sync_local_size: Optional[int] = None,
) -> str:
    """Evaluate sync action according to Gavel normative rules.

    Args:
        local_exists: Whether local save file exists.
        local_hash: Hash of local save file.
        local_mtime: Local file mtime float timestamp.
        local_size: Local file size in bytes.
        remote_save: Remote save metadata dictionary.
        last_sync_hash: Recorded baseline local file hash.
        last_sync_server_hash: Recorded baseline server hash.
        last_sync_local_size: Recorded baseline local file size.

    Returns:
        Uppercase action name: 'DOWNLOAD', 'UPLOAD', 'NO_OP', or 'CONFLICT'.
    """
    has_remote = remote_save is not None and isinstance(remote_save, dict)

    if not local_exists:
        if has_remote:
            return "DOWNLOAD"
        return "NO_OP"

    # Corrupt local save check (0 bytes or shrunken below 50% baseline size)
    if is_implausibly_shrunken(local_size, last_sync_local_size):
        logger.warning(
            "Local save file size (%s bytes) is implausibly shrunken compared to baseline (%s bytes)",
            local_size,
            last_sync_local_size,
        )
        if has_remote:
            return "DOWNLOAD"
        return "CONFLICT"

    if not has_remote:
        return "UPLOAD"

    remote_hash = remote_save.get("content_hash") if remote_save else None

    # Check byte identity disjunction (Provenance primary, Parity fallback)
    if local_matches_server(
        local_hash, remote_hash, last_sync_hash, last_sync_server_hash
    ):
        return "NO_OP"

    # When no baseline exists and both local and remote saves exist with differing hashes,
    # neither is an ancestor of the other -> must prompt conflict.
    if not last_sync_hash:
        return "CONFLICT"

    # Check if local file is unchanged since baseline while server save moved
    local_changed = (
        local_hash.lower() != last_sync_hash.lower()
    ) if local_hash else False
    server_changed = (
        not last_sync_server_hash
        or bool(remote_hash and remote_hash.lower() != last_sync_server_hash.lower())
    )

    if not local_changed and server_changed:
        return "DOWNLOAD"

    if local_changed and not server_changed:
        return "UPLOAD"

    return "CONFLICT"
