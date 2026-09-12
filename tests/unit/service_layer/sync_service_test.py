"""Unit tests for SyncService library synchronization, diff calculation, and cleanup."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from romm_steam_sync.adapters.romm_api import RomMTimeoutError
from romm_steam_sync.adapters.steam_vdf import SteamVdfManager, generate_app_id
from romm_steam_sync.config import AppSettings
from romm_steam_sync.domain import Rom
from romm_steam_sync.domain.sync_diff import SyncDiff
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.service_layer.sync_service import SyncService


def test_removeSyncedLibrary_cleansVdfAndArtworkAndDb(tmp_path):
    # Arrange
    steam_dir = tmp_path / "Steam"
    user_config_dir = steam_dir / "userdata" / "12345678" / "config"
    user_config_dir.mkdir(parents=True)
    grid_dir = user_config_dir / "grid"
    grid_dir.mkdir()

    vdf_path = user_config_dir / "shortcuts.vdf"
    db_path = tmp_path / "test.db"

    settings = AppSettings(
        romm_url="http://localhost:8080",
        steam_custom_path=str(steam_dir),
        steam_user_id="12345678",
    )
    db_session = DatabaseSession(db_path=db_path)

    app1_32, _, str_id1 = generate_app_id("retroarch.exe", "Final Fantasy VII")
    app2_32, _, str_id2 = generate_app_id("retroarch.exe", "Mario Kart 64")

    (grid_dir / f"{str_id1}p.png").write_bytes(b"dummy_art")
    (grid_dir / f"{str_id2}p.png").write_bytes(b"dummy_art")

    shortcuts = [
        {
            "AppName": "Final Fantasy VII",
            "Exe": '"retroarch.exe"',
            "tags": {"0": "RomM", "1": "PlayStation"},
            "appid": app1_32,
        },
        {
            "AppName": "Mario Kart 64",
            "Exe": '"retroarch.exe"',
            "tags": {"0": "RomM", "1": "Nintendo 64"},
            "appid": app2_32,
        },
    ]

    vdf_mgr = SteamVdfManager(str(vdf_path))
    vdf_mgr.save_shortcuts(shortcuts)

    with db_session as db:
        db.roms.add(Rom(rom_id=1, platform_slug="psx", name="Final Fantasy VII", shortcut_app_id=app1_32))
        db.roms.add(Rom(rom_id=2, platform_slug="n64", name="Mario Kart 64", shortcut_app_id=app2_32))
        db.commit()

    service = SyncService(settings=settings, db_session=db_session)

    # Act
    ok, msg, removed_count = service.remove_synced_library("PlayStation", skip_steam_guard=True)

    # Assert
    assert ok is True
    assert removed_count >= 1
    remaining = vdf_mgr.load_shortcuts()
    assert len(remaining) == 1
    assert remaining[0]["AppName"] == "Mario Kart 64"
    assert not (grid_dir / f"{str_id1}p.png").exists()
    assert (grid_dir / f"{str_id2}p.png").exists()


def test_getSyncedLibraries_deduplicatesBySlugAndTag(tmp_path):
    # Arrange
    steam_dir = tmp_path / "Steam"
    user_config_dir = steam_dir / "userdata" / "12345678" / "config"
    user_config_dir.mkdir(parents=True)
    vdf_path = user_config_dir / "shortcuts.vdf"
    db_path = tmp_path / "test.db"

    settings = AppSettings(
        romm_url="http://localhost:8080",
        steam_custom_path=str(steam_dir),
        steam_user_id="12345678",
    )
    db_session = DatabaseSession(db_path=db_path)

    shortcuts = [
        {
            "AppName": "Super Mario 64",
            "Exe": '"retroarch.exe"',
            "tags": {"0": "RomM", "1": "Nintendo 64"},
            "appid": 1001,
        },
    ]
    SteamVdfManager(str(vdf_path)).save_shortcuts(shortcuts)

    with db_session as db:
        db.roms.add(Rom(rom_id=10, platform_slug="n64", name="Super Mario 64", shortcut_app_id=1001))
        db.commit()

    service = SyncService(settings=settings, db_session=db_session)

    # Act
    libs = service.get_synced_libraries()

    # Assert
    assert len(libs) == 1
    assert libs[0]["name"] == "Nintendo 64"
    assert libs[0]["slug"] == "n64"
    assert libs[0]["count"] == 1


def test_getSyncedLibraries_deduplicatesGamecubeAndNgc(tmp_path):
    # Arrange
    steam_dir = tmp_path / "Steam"
    user_config_dir = steam_dir / "userdata" / "12345678" / "config"
    user_config_dir.mkdir(parents=True)
    vdf_path = user_config_dir / "shortcuts.vdf"
    db_path = tmp_path / "test.db"

    settings = AppSettings(
        romm_url="http://localhost:8080",
        steam_custom_path=str(steam_dir),
        steam_user_id="12345678",
    )
    db_session = DatabaseSession(db_path=db_path)

    shortcuts = [
        {
            "AppName": "Super Smash Bros. Melee",
            "Exe": '"retroarch.exe"',
            "tags": {"0": "RomM", "1": "GameCube"},
            "appid": 2001,
        },
    ]
    SteamVdfManager(str(vdf_path)).save_shortcuts(shortcuts)

    with db_session as db:
        db.roms.add(Rom(rom_id=20, platform_slug="ngc", name="Super Smash Bros. Melee", shortcut_app_id=2001))
        db.commit()

    service = SyncService(settings=settings, db_session=db_session)

    # Act
    libs = service.get_synced_libraries()

    # Assert
    assert len(libs) == 1
    assert libs[0]["name"] == "GameCube"
    assert libs[0]["slug"] == "gc"
    assert libs[0]["count"] == 1


def test_calculateSyncDiff_categorizesAdditionsRemovalsAndUnchanged(tmp_path):
    # Arrange
    db_path = tmp_path / "test.db"
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["ps2"],
    )

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    with service.db_session as db:
        db.roms.add(Rom(rom_id=1, platform_slug="ps2", name="Game 1 (Kept)"))
        db.roms.add(Rom(rom_id=2, platform_slug="ps2", name="Game 2 (Deleted from RomM)"))
        db.commit()

    shortcuts = [
        {
            "AppName": "Game 1 (Kept)",
            "Exe": '"/path/to/launcher"',
            "LaunchOptions": "--rom-id 1 --platform ps2",
            "tags": {"0": "RomM", "1": "PlayStation 2"},
        },
        {
            "AppName": "Game 2 (Deleted from RomM)",
            "Exe": '"/path/to/launcher"',
            "LaunchOptions": "--rom-id 2 --platform ps2",
            "tags": {"0": "RomM", "1": "PlayStation 2"},
        },
    ]

    all_roms = [
        {"id": 1, "name": "Game 1 (Kept)", "platform_slug": "ps2"},
        {"id": 3, "name": "Game 3 (New)", "platform_slug": "ps2"},
    ]

    # Act
    diff = service.calculate_sync_diff(
        enabled_platforms=["ps2"],
        all_roms=all_roms,
        shortcuts=shortcuts,
    )

    # Assert
    assert diff.total_additions == 1
    assert diff.total_removals == 1
    assert diff.total_unchanged == 1
    ps2_diff = diff.platform_diffs.get("ps2")
    assert ps2_diff is not None
    assert ps2_diff.additions[0]["id"] == 3
    assert ps2_diff.removals_roms[0].rom_id == 2
    assert ps2_diff.unchanged_roms[0]["id"] == 1


def test_syncLibrary_inFullMode_addsNewAndRemovesDeleted(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["snes"],
    )

    steam_dir = tmp_path / "Steam"
    grid_dir = steam_dir / "userdata" / "12345" / "config" / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    with service.db_session as db:
        db.roms.add(Rom(rom_id=1, platform_slug="snes", name="Game 1"))
        db.commit()

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "snes", "name": "Super Nintendo"}]
    mock_romm_client.get_roms.return_value = [{"id": 2, "name": "Game 2", "platform_slug": "snes"}]

    def mock_on_diff(diff: SyncDiff) -> str:
        return "full"

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(grid_dir.parent, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library(on_diff_callback=mock_on_diff)

    # Assert
    assert success is True
    assert "complete" in msg.lower()
    with service.db_session as db:
        assert db.roms.get(1) is None
        assert db.roms.get(2) is not None
        assert db.roms.get(2).name == "Game 2"


def test_syncLibrary_inAddOnlyMode_preservesMissingRoms(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["snes"],
    )

    steam_dir = tmp_path / "Steam"
    grid_dir = steam_dir / "userdata" / "12345" / "config" / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    with service.db_session as db:
        db.roms.add(Rom(rom_id=1, platform_slug="snes", name="Game 1"))
        db.commit()

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "snes", "name": "Super Nintendo"}]
    mock_romm_client.get_roms.return_value = [{"id": 2, "name": "Game 2", "platform_slug": "snes"}]

    def mock_on_diff(diff: SyncDiff) -> str:
        return "add_only"

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(grid_dir.parent, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library(on_diff_callback=mock_on_diff)

    # Assert
    assert success is True
    with service.db_session as db:
        assert db.roms.get(1) is not None
        assert db.roms.get(2) is not None


def test_syncLibrary_cancelAtDiffStage_abortsWithoutChanges(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["snes"],
    )

    steam_dir = tmp_path / "Steam"
    grid_dir = steam_dir / "userdata" / "12345" / "config" / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "snes", "name": "Super Nintendo"}]
    mock_romm_client.get_roms.return_value = [{"id": 5, "name": "Game 5", "platform_slug": "snes"}]

    def mock_on_diff(diff: SyncDiff) -> str:
        return "cancel"

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(grid_dir.parent, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library(on_diff_callback=mock_on_diff)

    # Assert
    assert success is False
    assert "cancelled" in msg.lower()
    with service.db_session as db:
        assert db.roms.get(5) is None


def test_syncLibrary_multiVersion_createsSingleShortcutAndPersistsAllRoms(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["ps1"],
    )

    steam_dir = tmp_path / "Steam"
    config_dir = steam_dir / "userdata" / "12345" / "config"
    grid_dir = config_dir / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    mock_roms = [
        {
            "id": 10,
            "name": "Final Fantasy VII (USA) (Disc 1)",
            "platform_slug": "ps1",
            "igdb_id": 1001,
            "sibling_roms": [{"id": 11}, {"id": 12}],
        },
        {
            "id": 11,
            "name": "Final Fantasy VII (USA) (Disc 2)",
            "platform_slug": "ps1",
            "igdb_id": 1001,
            "sibling_roms": [{"id": 10}, {"id": 12}],
        },
        {
            "id": 12,
            "name": "Final Fantasy VII (Europe)",
            "platform_slug": "ps1",
            "igdb_id": 1001,
            "sibling_roms": [{"id": 10}, {"id": 11}],
        },
    ]

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "ps1", "name": "PlayStation"}]
    mock_romm_client.get_roms.return_value = mock_roms

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(config_dir, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library()

    # Assert
    assert success is True
    assert count == 1
    vdf_path = config_dir / "shortcuts.vdf"
    assert vdf_path.exists()
    shortcuts = SteamVdfManager(str(vdf_path)).load_shortcuts()
    assert len(shortcuts) == 1

    with service.db_session as db:
        r10 = db.roms.get(10)
        r11 = db.roms.get(11)
        r12 = db.roms.get(12)
        assert r10 is not None
        assert r11 is not None
        assert r12 is not None
        assert r10.sibling_group_key == "igdb:1001:ps1"
        assert r10.shortcut_app_id is not None
        assert r11.shortcut_app_id is None


def test_syncLibrary_multiVersion_honorsSavedDefaultPreference(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["ps1"],
    )

    steam_dir = tmp_path / "Steam"
    config_dir = steam_dir / "userdata" / "12345" / "config"
    grid_dir = config_dir / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    with service.db_session as db:
        db.kv_config.set("default_version:igdb:1001:ps1", "11")
        db.commit()

    mock_roms = [
        {
            "id": 10,
            "name": "Final Fantasy VII (USA) (Disc 1)",
            "platform_slug": "ps1",
            "igdb_id": 1001,
            "sibling_roms": [{"id": 11}],
        },
        {
            "id": 11,
            "name": "Final Fantasy VII (USA) (Disc 2)",
            "platform_slug": "ps1",
            "igdb_id": 1001,
            "sibling_roms": [{"id": 10}],
        },
    ]

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "ps1", "name": "PlayStation"}]
    mock_romm_client.get_roms.return_value = mock_roms

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(config_dir, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library()

    # Assert
    assert success is True
    with service.db_session as db:
        r10 = db.roms.get(10)
        r11 = db.roms.get(11)
        assert r11.shortcut_app_id is not None
        assert r10.shortcut_app_id is None


def test_syncLibrary_cancellationKeep_retainsProcessedItems(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["snes"],
    )

    steam_dir = tmp_path / "Steam"
    grid_dir = steam_dir / "userdata" / "12345" / "config" / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "snes", "name": "Super Nintendo"}]
    mock_romm_client.get_roms.return_value = [
        {"id": 1, "name": "Game 1", "platform_slug": "snes"},
        {"id": 2, "name": "Game 2", "platform_slug": "snes"},
    ]

    call_count = 0

    def cancel_check():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            return "cancel"
        return None

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(grid_dir.parent, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library(is_cancelled_callback=cancel_check)

    # Assert
    assert success is False
    assert "cancelled" in msg.lower()
    assert count == 1


def test_syncLibrary_cancellationRollback_restoresBackup(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["snes"],
    )

    steam_dir = tmp_path / "Steam"
    grid_dir = steam_dir / "userdata" / "12345" / "config" / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)
    service.backup_manager = MagicMock()
    service.backup_manager.create_backup.return_value = "backup_123"

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "snes", "name": "Super Nintendo"}]
    mock_romm_client.get_roms.return_value = [
        {"id": 1, "name": "Game 1", "platform_slug": "snes"},
    ]

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(grid_dir.parent, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library(is_cancelled_callback=lambda: "rollback")

    # Assert
    assert success is False
    assert "reverted" in msg.lower() or "backup" in msg.lower()
    service.backup_manager.restore_backup.assert_called_once_with("backup_123", str(grid_dir.parent))


def test_syncLibrary_artwork_downloadsAndPersistsAssets(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steamgriddb_api_key="mock_sgdb_key",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["snes"],
    )

    steam_dir = tmp_path / "Steam"
    grid_dir = steam_dir / "userdata" / "12345" / "config" / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "snes", "name": "Super Nintendo"}]
    mock_romm_client.get_roms.return_value = [
        {
            "id": 99,
            "name": "Super Mario World",
            "platform_slug": "snes",
            "igdb_id": 1001,
            "cover_url": "http://romm/cover.png",
        }
    ]

    mock_sgdb_client = MagicMock()
    mock_sgdb_client.get_game_by_igdb_id.return_value = 5555
    mock_sgdb_client.get_asset_url.side_effect = lambda asset_type, sgdb_id: f"http://sgdb/{asset_type}.png"

    def mock_download_image(url, path):
        with open(path, "wb") as f:
            f.write(b"mock_sgdb_image")
        return True

    mock_sgdb_client.download_image.side_effect = mock_download_image

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGridDbClient", return_value=mock_sgdb_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(grid_dir.parent, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library()

    # Assert
    assert success is True
    assert count == 1
    files = [f.name for f in grid_dir.glob("*.png")]
    assert len(files) >= 4
    assert any("_hero.png" in f for f in files)
    assert any("_logo.png" in f for f in files)
    assert any("_icon.png" in f for f in files)
    assert any(f.endswith("p.png") for f in files)


def test_syncLibrary_timeoutCallbackRevertBackup_rollsBackOnTimeout(tmp_path, monkeypatch):
    # Arrange
    settings = MagicMock()
    settings.steam_user_id = "123456"
    settings.steam_custom_path = ""
    settings.romm_url = "http://mock-romm:5500"
    settings.api_key = ""
    settings.enabled_platforms = ["snes"]

    config_dir = tmp_path / "userdata" / "123456" / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    vdf_file = config_dir / "shortcuts.vdf"
    vdf_file.write_bytes(b"initial_vdf_content")

    monkeypatch.setattr("romm_steam_sync.adapters.steam_path.SteamPathResolver.get_user_config_dir", lambda **k: (config_dir, "123456"))
    monkeypatch.setattr("romm_steam_sync.adapters.steam_guard.SteamGuard.is_steam_running", lambda: False)

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient") as mock_client_cls:
        client_inst = mock_client_cls.return_value
        client_inst.authenticate.return_value = (True, "OK")
        client_inst.get_platforms.return_value = [{"id": 1, "name": "SNES", "slug": "snes"}]
        client_inst.get_roms.side_effect = RomMTimeoutError("RomM timeout")
        service = SyncService(settings=settings)

        # Act
        success, msg, count = service.sync_library(skip_steam_guard=True, on_timeout_callback=lambda p, b: "revert")

    # Assert
    assert success is False
    assert "Reverted Steam configuration" in msg
    assert count == 0


def test_syncLibrary_extendedProgressCallback_receivesCoverAndRomName(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["snes"],
    )
    steam_dir = tmp_path / "Steam"
    grid_dir = steam_dir / "userdata" / "12345" / "config" / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "snes", "name": "Super Nintendo"}]
    mock_romm_client.get_roms.return_value = [
        {"id": 10, "name": "Chrono Trigger", "platform_slug": "snes", "cover_url": "http://romm/chrono.png"}
    ]

    received_progress = []

    def ext_progress_cb(pct, msg, cover_path=None, rom_name=None):
        received_progress.append((pct, msg, cover_path, rom_name))

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(grid_dir.parent, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library(progress_callback=ext_progress_cb)

    # Assert
    assert success is True
    assert count == 1
    rom_entries = [p for p in received_progress if p[3] == "Chrono Trigger"]
    assert len(rom_entries) == 1
    assert rom_entries[0][3] == "Chrono Trigger"


def test_syncLibrary_legacy2argProgressCallback_supportedSeamlessly(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["snes"],
    )
    steam_dir = tmp_path / "Steam"
    grid_dir = steam_dir / "userdata" / "12345" / "config" / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "snes", "name": "Super Nintendo"}]
    mock_romm_client.get_roms.return_value = [
        {"id": 11, "name": "Zelda", "platform_slug": "snes"}
    ]

    legacy_progress = []

    def legacy_cb(pct, msg):
        legacy_progress.append((pct, msg))

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(grid_dir.parent, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library(progress_callback=legacy_cb)

    # Assert
    assert success is True
    assert len(legacy_progress) > 0


def test_syncLibrary_emitsCalculatingChangesProgress(tmp_path):
    # Arrange
    settings = AppSettings(
        romm_url="http://mock-romm:8080",
        steam_custom_path=str(tmp_path / "Steam"),
        enabled_platforms=["snes"],
    )
    steam_dir = tmp_path / "Steam"
    grid_dir = steam_dir / "userdata" / "12345" / "config" / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    service = SyncService(settings=settings)
    service.db_session = DatabaseSession(db_path=db_path)

    mock_romm_client = MagicMock()
    mock_romm_client.authenticate.return_value = (True, "OK")
    mock_romm_client.get_platforms.return_value = [{"id": 1, "slug": "snes", "name": "Super Nintendo"}]
    mock_romm_client.get_roms.return_value = [{"id": 1, "name": "Chrono Trigger", "platform_slug": "snes"}]

    received_messages = []

    def progress_cb(pct, msg, cover_path=None, rom_name=None):
        received_messages.append((pct, msg))

    with patch("romm_steam_sync.service_layer.sync_service.RomMApiClient", return_value=mock_romm_client), \
         patch("romm_steam_sync.service_layer.sync_service.SteamPathResolver.get_user_config_dir", return_value=(grid_dir.parent, "12345")), \
         patch("romm_steam_sync.service_layer.sync_service.SteamGuard.is_steam_running", return_value=False):

        # Act
        success, msg, count = service.sync_library(progress_callback=progress_cb)

    # Assert
    assert success is True
    calc_msgs = [m for m in received_messages if "calculating library changes" in m[1].lower()]
    assert len(calc_msgs) == 1
    assert calc_msgs[0][1] == "Checking RomM library and calculating library changes..."


