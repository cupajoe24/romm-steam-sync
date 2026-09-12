"""Integration tests for DatabaseSession and Repositories."""

from romm_steam_sync.domain import Rom, RomInstall, SyncRun
from romm_steam_sync.service_layer.db_session import DatabaseSession


def test_database_session_transactions(tmp_path):
    db_path = tmp_path / "test_romm_sync.db"
    db_session = DatabaseSession(db_path=db_path)

    # 1. Add Rom, RomInstall, and SyncRun within transaction session
    with db_session as db:
        rom = Rom(
            rom_id=200,
            platform_slug="gba",
            name="Pokemon Emerald",
            shortcut_app_id=-987654,
        )
        db.roms.add(rom)

        install = RomInstall(
            rom_id=200,
            file_path="/tmp/pokemon.gba",
            rom_dir="/tmp",
            launchable=True,
        )
        db.installs.add(install)

        run = SyncRun.start_new()
        run.complete(1)
        db.sync_runs.add(run)

        db.commit()

    # 2. Verify persistence in new session
    with db_session as db:
        fetched_rom = db.roms.get(200)
        assert fetched_rom is not None
        assert fetched_rom.name == "Pokemon Emerald"
        assert fetched_rom.platform_slug == "gba"
        assert fetched_rom.shortcut_app_id == -987654

        fetched_install = db.installs.get(200)
        assert fetched_install is not None
        assert fetched_install.file_path == "/tmp/pokemon.gba"
        assert fetched_install.launchable is True

