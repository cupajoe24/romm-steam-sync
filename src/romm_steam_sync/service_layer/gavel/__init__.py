"""Gavel Save-Sync Decision Engine Package.

Based on and ported from romm-gavel (https://github.com/danielcopper/romm-gavel).
Copyright (c) 2026 danielcopper.
Licensed under the MIT License.
"""

from romm_steam_sync.service_layer.gavel.decision_table import (
    SHRINK_RATIO,
    compute_sync_action,
    is_implausibly_shrunken,
    parse_iso_to_epoch,
)
from romm_steam_sync.service_layer.gavel.ladder import (
    local_matches_server,
    resolve_upload_conflict,
)

__all__ = [
    "SHRINK_RATIO",
    "compute_sync_action",
    "is_implausibly_shrunken",
    "parse_iso_to_epoch",
    "local_matches_server",
    "resolve_upload_conflict",
]
