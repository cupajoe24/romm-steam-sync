"""Unit tests for MemoryCardPerGameStrategy and handler registration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from romm_steam_sync.domain import RomSaveSyncState
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.service_layer.save_strategies.default_save_per_game import calculate_save_hash
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin import (
    DolphinGameCubeHandler,
)
from romm_steam_sync.service_layer.save_strategies.memory_card_per_game import (
    GenericMemoryCardHandler,
    MemoryCardPerGameStrategy,
    get_handler,
)
from romm_steam_sync.service_layer.save_strategies.registry import (
    SAVE_STRATEGY_REGISTRY,
    get_save_strategy,
)


def _create_dummy_gc_disc(
    path: Path,
    game_code: str = "GM8E",
    maker_code: str = "01",
    title: str = "Mario Party 8",
) -> Path:
    header = bytearray(0x60)
    header[0:4] = game_code.encode("latin1")
    header[4:6] = maker_code.encode("latin1")
    header[0x1C:0x20] = b"\xc2\x33\x9f\x3d"
    title_bytes = title.encode("latin1")
    header[0x20 : 0x20 + len(title_bytes)] = title_bytes
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)
    return path


def _create_dummy_gci(
    path: Path,
    game_code: str = "GM8E",
    maker_code: str = "01",
) -> Path:
    header = bytearray(0x28)
    header[0:4] = game_code.encode("latin1")
    header[4:6] = maker_code.encode("latin1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header)
    return path


def test_getSaveStrategy_resolvesGamecubeStrategy():
    # Arrange & Act
    strat_core = get_save_strategy(core_name="dolphin_libretro")
    strat_core_dll = get_save_strategy(core_name="dolphin_libretro.dll")
    strat_gc = get_save_strategy(platform_slug="gc")
    strat_ngc = get_save_strategy(platform_slug="ngc")
    strat_gamecube = get_save_strategy(platform_slug="gamecube")
    strat_explicit = get_save_strategy(strategy_name="memory_card_per_game")

    # Assert
    assert "memory_card_per_game" in SAVE_STRATEGY_REGISTRY
    assert isinstance(SAVE_STRATEGY_REGISTRY["memory_card_per_game"], MemoryCardPerGameStrategy)
    assert strat_core.name == "memory_card_per_game"
    assert strat_core_dll.name == "memory_card_per_game"
    assert strat_gc.name == "memory_card_per_game"
    assert strat_ngc.name == "memory_card_per_game"
    assert strat_gamecube.name == "memory_card_per_game"
    assert strat_explicit.name == "memory_card_per_game"


def test_getHandler_resolvesDolphinAndFallbackGenericHandler():
    # Arrange & Act
    h_core = get_handler(core_name="dolphin_libretro")
    h_slug = get_handler(platform_slug="gc")
    h_fallback = get_handler(core_name="unmapped_fantasy_core")

    # Assert
    assert isinstance(h_core, DolphinGameCubeHandler)
    assert isinstance(h_slug, DolphinGameCubeHandler)
    assert isinstance(h_fallback, GenericMemoryCardHandler)


def test_syncPreLaunch_downloadsRemoteSave(tmp_path):
    # Arrange
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "Games" / "Mario Party 8.iso"
    _create_dummy_gc_disc(rom_file, game_code="GM8E", maker_code="01", title="Mario Party 8")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = [
        {"id": 201, "name": "01-GM8E-MarioParty8.gci", "content_hash": "remote_hash_123"}
    ]

    def fake_download(save_id, target_path):
        _create_dummy_gci(Path(target_path), game_code="GM8E", maker_code="01")
        return True

    mock_client.download_save_content.side_effect = fake_download
    strat = MemoryCardPerGameStrategy()

    with patch(
        "romm_steam_sync.service_layer.save_strategies.handlers.dolphin.RetroArchLauncher.resolve_retroarch_binary",
        return_value=str(ra_exe),
    ):
        # Act
        action, msg, remote_save, target_path = strat.sync_pre_launch(
            rom_id=77,
            rom_path=str(rom_file),
            platform_slug="gc",
            client=mock_client,
            configured_retroarch_path=str(ra_exe),
        )

    # Assert
    assert action == "DOWNLOAD"
    expected_dest = ra_dir / "saves" / "dolphin-emu" / "User" / "GC" / "USA" / "Card A" / "01-GM8E-MarioParty8.gci"
    assert target_path == expected_dest
    assert target_path.exists()
    mock_client.download_save_content.assert_called_once_with(201, str(expected_dest))


def test_syncPreLaunch_quarantinesStaleLocalSave(tmp_path):
    # Arrange
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "Games" / "Mario Party 8.iso"
    _create_dummy_gc_disc(rom_file, game_code="GM8E", maker_code="01", title="Mario Party 8")

    card_a_dir = ra_dir / "saves" / "dolphin-emu" / "User" / "GC" / "USA" / "Card A"
    card_a_dir.mkdir(parents=True, exist_ok=True)
    existing_save = card_a_dir / "01-GM8E-MarioParty8.gci"
    existing_save.write_bytes(b"old save bytes")

    old_local_hash = calculate_save_hash(str(existing_save))
    db_file = tmp_path / "test.db"

    with patch("romm_steam_sync.service_layer.db_session.get_default_db_path", return_value=db_file):
        with DatabaseSession() as db:
            st = RomSaveSyncState(rom_id=78, active_slot="autosave")
            st.adopt_baseline(
                file_name="01-GM8E-MarioParty8.gci",
                last_sync_hash=old_local_hash,
                last_sync_server_hash="old_server_hash",
                last_sync_local_size=existing_save.stat().st_size,
                last_sync_local_mtime=existing_save.stat().st_mtime,
            )
            db.save_sync_states.add(st)
            db.commit()

        mock_client = MagicMock()
        mock_client.get_saves.return_value = [
            {"id": 202, "name": "01-GM8E-MarioParty8.gci", "content_hash": "newer_remote_hash"}
        ]

        def fake_download(save_id, target_path):
            Path(target_path).write_bytes(b"new downloaded save bytes")
            return True

        mock_client.download_save_content.side_effect = fake_download
        strat = MemoryCardPerGameStrategy()

        with patch(
            "romm_steam_sync.service_layer.save_strategies.handlers.dolphin.RetroArchLauncher.resolve_retroarch_binary",
            return_value=str(ra_exe),
        ):
            # Act
            action, msg, remote_save, target_path = strat.sync_pre_launch(
                rom_id=78,
                rom_path=str(rom_file),
                platform_slug="gc",
                client=mock_client,
                configured_retroarch_path=str(ra_exe),
            )

        # Assert
        assert action == "DOWNLOAD"
        assert target_path.read_bytes() == b"new downloaded save bytes"
        backup_dir = card_a_dir / ".romm-backup"
        assert backup_dir.exists()
        backups = list(backup_dir.glob("*.gci"))
        assert len(backups) == 1
        assert backups[0].read_bytes() == b"old save bytes"


def test_syncPostLaunch_uploadsGameplaySave(tmp_path):
    # Arrange
    ra_dir = tmp_path / "RetroArch"
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.parent.mkdir(parents=True, exist_ok=True)
    ra_exe.write_bytes(b"dummy")

    rom_file = tmp_path / "Games" / "Mario Party 8.iso"
    _create_dummy_gc_disc(rom_file, game_code="GM8E", maker_code="01", title="Mario Party 8")

    card_a_dir = ra_dir / "saves" / "dolphin-emu" / "User" / "GC" / "USA" / "Card A"
    card_a_dir.mkdir(parents=True, exist_ok=True)
    save_file = card_a_dir / "01-GM8E-MarioParty8.gci"
    save_file.write_bytes(b"new gameplay save data")

    mock_client = MagicMock()
    mock_client.get_saves.return_value = [{"id": 201, "name": "01-GM8E-MarioParty8.gci"}]
    mock_client.upload_save.return_value = {"id": 201, "content_hash": "hash_after_upload"}
    strat = MemoryCardPerGameStrategy()
    db_file = tmp_path / "test.db"

    with patch("romm_steam_sync.service_layer.db_session.get_default_db_path", return_value=db_file):
        with patch(
            "romm_steam_sync.service_layer.save_strategies.handlers.dolphin.RetroArchLauncher.resolve_retroarch_binary",
            return_value=str(ra_exe),
        ):
            # Act
            success, msg = strat.sync_post_launch(
                rom_id=77,
                save_path=str(rom_file),
                client=mock_client,
                platform_slug="gc",
                configured_retroarch_path=str(ra_exe),
            )

            # Assert
            assert success is True
            mock_client.upload_save.assert_called_once_with(
                77, str(save_file), save_id=201, slot="autosave"
            )


def test_genericMemoryCardHandler_get_save_directories_macOsPath(tmp_path):
    # Arrange
    fake_home = tmp_path / "home"
    mac_saves = fake_home / "Library" / "Application Support" / "RetroArch" / "saves"
    mac_saves.mkdir(parents=True)

    handler = GenericMemoryCardHandler()
    with patch("romm_steam_sync.service_layer.save_strategies.memory_card_per_game.sys.platform", "darwin"), \
         patch("romm_steam_sync.service_layer.save_strategies.memory_card_per_game.Path.home", return_value=fake_home):
        dirs = handler.get_save_directories()
        assert mac_saves in dirs

