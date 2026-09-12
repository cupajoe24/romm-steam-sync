"""Unit tests for RomSaveSyncState and FileSyncState domain models."""

from romm_steam_sync.domain.save_sync_state import FileSyncState, RomSaveSyncState


def test_adoptBaseline_recordsFileState():
    # Arrange
    state = RomSaveSyncState(rom_id=42)

    # Act
    state.adopt_baseline(
        file_name="game.srm",
        last_sync_hash="abc123hash",
        last_sync_server_hash="srv123hash",
        last_sync_local_size=2048,
        last_sync_local_mtime=1690000000.0,
        tracked_save_id=99,
    )

    # Assert
    file_state = state.get_file_state("game.srm")
    assert file_state is not None
    assert file_state.file_name == "game.srm"
    assert file_state.last_sync_hash == "abc123hash"
    assert file_state.last_sync_server_hash == "srv123hash"
    assert file_state.last_sync_local_size == 2048
    assert file_state.tracked_save_id == 99
    assert file_state.last_synced_at is not None


def test_updateFileState_replacesExistingEntry():
    # Arrange
    state = RomSaveSyncState(rom_id=42)
    initial_f = FileSyncState(file_name="game.srm", last_sync_hash="hash1")
    updated_f = FileSyncState(file_name="game.srm", last_sync_hash="hash2")

    # Act
    state.update_file_state(initial_f)
    first_lookup = state.get_file_state("game.srm")
    state.update_file_state(updated_f)
    second_lookup = state.get_file_state("game.srm")

    # Assert
    assert first_lookup.last_sync_hash == "hash1"
    assert second_lookup.last_sync_hash == "hash2"
