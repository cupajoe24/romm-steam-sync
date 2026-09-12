"""Unit tests for DatabaseSession and aggregate repositories."""

from romm_steam_sync.domain import Rom, RomInstall, RomSaveSyncState, SyncRun
from romm_steam_sync.domain.kv_config import KvConfig
from romm_steam_sync.service_layer.db_session import DatabaseSession


def test_listAll_returnsPersistedInstallations(tmp_path):
    # Arrange
    db_path = tmp_path / "test_installs.db"
    with DatabaseSession(db_path) as db:
        install1 = RomInstall(rom_id=101, file_path=str(tmp_path / "game1.z64"), rom_dir=str(tmp_path))
        install2 = RomInstall(rom_id=102, file_path=str(tmp_path / "game2.gba"), rom_dir=str(tmp_path))
        db.installs.add(install1)
        db.installs.add(install2)
        db.commit()

    # Act
    with DatabaseSession(db_path) as db:
        all_installs = db.installs.list_all()

    # Assert
    assert len(all_installs) == 2
    rom_ids = {i.rom_id for i in all_installs}
    assert rom_ids == {101, 102}


def test_addAndGet_persistsRom(tmp_path):
    # Arrange
    db_path = tmp_path / "test_roms.db"
    rom = Rom(rom_id=42, platform_slug="snes", name="Super Mario World")

    # Act
    with DatabaseSession(db_path) as db:
        db.roms.add(rom)
        db.commit()

    with DatabaseSession(db_path) as db:
        loaded = db.roms.get(42)

    # Assert
    assert loaded is not None
    assert loaded.rom_id == 42
    assert loaded.name == "Super Mario World"


def test_setAndGet_persistsKeyValue(tmp_path):
    # Arrange
    db_path = tmp_path / "test_kv.db"

    # Act
    with DatabaseSession(db_path) as db:
        db.kv_config.set("custom_key", "custom_val")
        db.commit()

    with DatabaseSession(db_path) as db:
        val = db.kv_config.get("custom_key")

    # Assert
    assert val is not None
    assert val.value == "custom_val"


def test_addAndGet_persistsBaselineState(tmp_path):
    # Arrange
    db_path = tmp_path / "test_gavel.db"
    with DatabaseSession(db_path) as db:
        state = RomSaveSyncState(rom_id=42, active_slot="autosave")
        state.adopt_baseline(
            file_name="game.srm",
            last_sync_hash="hash_abc",
            last_sync_server_hash="server_hash_xyz",
            last_sync_local_size=8192,
            last_sync_local_mtime=12345678.0,
            tracked_save_id=99,
        )

        # Act
        db.save_sync_states.add(state)
        db.commit()

    # Assert
    with DatabaseSession(db_path) as db:
        fetched = db.save_sync_states.get(42)
        assert fetched is not None
        assert fetched.rom_id == 42
        assert fetched.active_slot == "autosave"
        fstate = fetched.get_file_state("game.srm")
        assert fstate is not None
        assert fstate.last_sync_hash == "hash_abc"
        assert fstate.last_sync_server_hash == "server_hash_xyz"
        assert fstate.last_sync_local_size == 8192
        assert fstate.last_sync_local_mtime == 12345678.0
        assert fstate.tracked_save_id == 99
