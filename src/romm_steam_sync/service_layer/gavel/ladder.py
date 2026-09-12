"""The 409 resolution ladder and the identity check — Gavel normative core.

Ported from romm-gavel (https://github.com/danielcopper/romm-gavel).
Copyright (c) 2026 danielcopper. Licensed under the MIT License.
"""

from typing import Literal, Optional


def local_matches_server(
    local_hash: Optional[str],
    server_content_hash: Optional[str],
    last_sync_hash: Optional[str],
    last_sync_server_hash: Optional[str],
) -> bool:
    """Evaluate whether the present local file is byte-identical to a server save.

    A disjunction of two routes:
    - Provenance (primary): local file is unchanged since recorded baseline
      (local_hash == last_sync_hash) AND that baseline was synced against this
      exact server content (last_sync_server_hash == server_content_hash).
    - Parity (fallback): local_hash == server_content_hash directly.

    Args:
        local_hash: Hash of local save file.
        server_content_hash: Content hash of remote server save.
        last_sync_hash: Recorded baseline local file hash.
        last_sync_server_hash: Recorded baseline server hash.

    Returns:
        True if local file matches server save content, False otherwise.
    """
    if not local_hash or not server_content_hash:
        return False

    # Provenance (primary route)
    if (
        last_sync_hash
        and last_sync_server_hash
        and local_hash.lower() == last_sync_hash.lower()
        and last_sync_server_hash.lower() == server_content_hash.lower()
    ):
        return True

    # Parity (fallback route)
    return local_hash.lower() == server_content_hash.lower()


def resolve_upload_conflict(
    local_hash: Optional[str],
    server_content_hash: Optional[str],
    last_sync_hash: Optional[str],
    last_sync_server_hash: Optional[str],
) -> Literal["download", "conflict"]:
    """Resolve an HTTP 409 on an automatic upload POST (overwrite=false).

    L1 — local file unchanged since baseline (local_hash == last_sync_hash):
         client holds no un-synced work -> download.
    L2 — byte-identical to server head (local_matches_server):
         adopting identical bytes loses nothing -> download.
    Otherwise -> conflict.

    Args:
        local_hash: Hash of local file.
        server_content_hash: Hash of server save head.
        last_sync_hash: Recorded baseline local hash.
        last_sync_server_hash: Recorded baseline server hash.

    Returns:
        Resolution action: 'download' or 'conflict'.
    """
    if (
        local_hash
        and last_sync_hash
        and local_hash.lower() == last_sync_hash.lower()
    ):
        return "download"

    if local_matches_server(
        local_hash, server_content_hash, last_sync_hash, last_sync_server_hash
    ):
        return "download"

    return "conflict"
