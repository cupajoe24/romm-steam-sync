"""Unit tests for Gavel conflict resolution ladder."""

from romm_steam_sync.service_layer.gavel.ladder import (
    local_matches_server,
    resolve_upload_conflict,
)


def test_localMatchesServer_provenance_returnsTrueWhenBaselinesMatch():
    # Arrange & Act
    matches = local_matches_server(
        local_hash="local_md5_abc",
        server_content_hash="server_sha_123",
        last_sync_hash="local_md5_abc",
        last_sync_server_hash="server_sha_123",
    )

    # Assert
    assert matches is True


def test_localMatchesServer_parity_returnsTrueWhenHashesEqual():
    # Arrange & Act
    matches = local_matches_server(
        local_hash="hash_123",
        server_content_hash="HASH_123",
        last_sync_hash=None,
        last_sync_server_hash=None,
    )

    # Assert
    assert matches is True


def test_localMatchesServer_mismatch_returnsFalseWhenDiverged():
    # Arrange & Act
    matches = local_matches_server(
        local_hash="local_changed",
        server_content_hash="server_new",
        last_sync_hash="local_old",
        last_sync_server_hash="server_old",
    )

    # Assert
    assert matches is False


def test_resolveUploadConflict_evaluatesLadderRules():
    # Arrange & Act
    # L1: local file unchanged since baseline -> download
    l1_action = resolve_upload_conflict(
        local_hash="baseline_hash",
        server_content_hash="server_moved_ahead",
        last_sync_hash="baseline_hash",
        last_sync_server_hash="server_old",
    )

    # L2: local file byte-identical to server head -> download
    l2_action = resolve_upload_conflict(
        local_hash="server_moved_ahead",
        server_content_hash="server_moved_ahead",
        last_sync_hash="baseline_old",
        last_sync_server_hash="server_old",
    )

    # Both edited independently -> conflict
    conflict_action = resolve_upload_conflict(
        local_hash="local_new_edits",
        server_content_hash="server_moved_ahead",
        last_sync_hash="baseline_hash",
        last_sync_server_hash="server_old",
    )

    # Assert
    assert l1_action == "download"
    assert l2_action == "download"
    assert conflict_action == "conflict"
