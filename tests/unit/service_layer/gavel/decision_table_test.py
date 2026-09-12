"""Unit tests for Gavel decision table synchronization evaluation."""

from romm_steam_sync.service_layer.gavel.decision_table import (
    compute_sync_action,
    is_implausibly_shrunken,
    parse_iso_to_epoch,
)


def test_isImplausiblyShrunken_evaluatesSizeShrinkRatio():
    # Arrange & Act & Assert
    assert is_implausibly_shrunken(0, 1000) is True
    assert is_implausibly_shrunken(400, 1000) is True
    assert is_implausibly_shrunken(600, 1000) is False
    assert is_implausibly_shrunken(100, None) is False


def test_computeSyncAction_evaluatesMatrixOutcomes():
    # Arrange
    local_newer_mtime = parse_iso_to_epoch("2026-08-02T12:00:00Z")

    # Act & Assert
    # 1. Download fresh remote
    assert compute_sync_action(
        local_exists=False,
        local_hash=None,
        local_mtime=None,
        local_size=None,
        remote_save={"id": 1, "content_hash": "abc"},
    ) == "DOWNLOAD"

    # 2. Upload initial local
    assert compute_sync_action(
        local_exists=True,
        local_hash="abc",
        local_mtime=100.0,
        local_size=1000,
        remote_save=None,
    ) == "UPLOAD"

    # 3. Corrupt 0-byte local file with remote save available -> DOWNLOAD
    assert compute_sync_action(
        local_exists=True,
        local_hash="d41d8cd98f00b204e9800998ecf8427e",
        local_mtime=200.0,
        local_size=0,
        remote_save={"id": 1, "content_hash": "abc"},
        last_sync_local_size=1000,
    ) == "DOWNLOAD"

    # 4. Identity match via Provenance -> NO_OP
    assert compute_sync_action(
        local_exists=True,
        local_hash="local_md5",
        local_mtime=100.0,
        local_size=1000,
        remote_save={"id": 1, "content_hash": "server_digest"},
        last_sync_hash="local_md5",
        last_sync_server_hash="server_digest",
    ) == "NO_OP"

    # 5. Local unchanged since baseline, server save updated -> DOWNLOAD
    assert compute_sync_action(
        local_exists=True,
        local_hash="baseline_hash",
        local_mtime=100.0,
        local_size=1000,
        remote_save={"id": 1, "content_hash": "new_server_hash", "updated_at": "2026-08-23T12:00:00Z"},
        last_sync_hash="baseline_hash",
        last_sync_server_hash="old_server_hash",
    ) == "DOWNLOAD"

    # 6. Local modified newer -> UPLOAD
    assert compute_sync_action(
        local_exists=True,
        local_hash="new_local_hash",
        local_mtime=local_newer_mtime,
        local_size=1000,
        remote_save={"id": 1, "content_hash": "old_remote_hash", "updated_at": "2026-08-01T12:00:00Z"},
        last_sync_hash="old_local_hash",
        last_sync_server_hash="old_remote_hash",
    ) == "UPLOAD"

    # 7. No baseline exists and both local and remote exist with differing hashes -> CONFLICT
    assert compute_sync_action(
        local_exists=True,
        local_hash="offline_local_hash",
        local_mtime=100.0,
        local_size=1000,
        remote_save={"id": 1, "content_hash": "romm_remote_hash", "updated_at": "2026-08-01T12:00:00Z"},
        last_sync_hash=None,
        last_sync_server_hash=None,
    ) == "CONFLICT"

    # 8. Both local and server modified independently since baseline -> CONFLICT
    assert compute_sync_action(
        local_exists=True,
        local_hash="new_local_hash_2",
        local_mtime=200.0,
        local_size=1000,
        remote_save={"id": 1, "content_hash": "new_remote_hash_2", "updated_at": "2026-08-05T12:00:00Z"},
        last_sync_hash="old_baseline_hash",
        last_sync_server_hash="old_server_hash",
    ) == "CONFLICT"
