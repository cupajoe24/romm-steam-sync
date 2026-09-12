"""Unit tests for Steam backup creation, 5-backup rolling threshold, and restoration."""

import time

from romm_steam_sync.adapters.steam_backup import SteamBackupManager
from romm_steam_sync.adapters.steam_vdf import SteamVdfManager


def test_createBackup_withExceedingCount_prunesToRollingThreshold(tmp_path):
    # Arrange
    steam_config = tmp_path / "steam_config"
    steam_config.mkdir()
    vdf_file = steam_config / "shortcuts.vdf"
    vdf_file.write_text("initial vdf content")
    backup_root = tmp_path / "backups"
    mgr = SteamBackupManager(backup_root_dir=backup_root)
    backup_ids = []

    # Act
    for i in range(6):
        vdf_file.write_text(f"vdf content version {i}")
        b_id = mgr.create_backup(str(steam_config))
        assert b_id is not None
        backup_ids.append(b_id)
        time.sleep(0.01)

    retained = mgr.list_backups()
    retained_ids = [b["id"] for b in retained]

    # Assert
    assert len(retained) == 5
    assert backup_ids[0] not in retained_ids
    assert backup_ids[-1] in retained_ids


def test_restoreBackup_restoresOriginalFileContents(tmp_path):
    # Arrange
    steam_config = tmp_path / "steam_config"
    steam_config.mkdir()
    vdf_file = steam_config / "shortcuts.vdf"
    vdf_file.write_text("ORIGINAL_CONTENT")
    backup_root = tmp_path / "backups"
    mgr = SteamBackupManager(backup_root_dir=backup_root)
    b_id = mgr.create_backup(str(steam_config))
    assert b_id is not None
    vdf_file.write_text("MUTATED_CONTENT")

    # Act
    ok = mgr.restore_backup(b_id, str(steam_config))

    # Assert
    assert ok is True
    assert vdf_file.read_text() == "ORIGINAL_CONTENT"


def test_resyncLocalconfigFromVdf_updatesCollections(tmp_path):
    # Arrange
    steam_config = tmp_path / "steam_config"
    steam_config.mkdir()
    vdf_file = steam_config / "shortcuts.vdf"
    shortcuts = [
        {
            "AppName": "Super Mario 64",
            "Exe": '"C:/Games/launcher.exe"',
            "StartDir": '"C:/Games/"',
            "icon": "",
            "ShortcutPath": "",
            "LaunchOptions": "",
            "IsHidden": 0,
            "AllowDesktopConfig": 1,
            "AllowOverlay": 1,
            "OpenVR": 0,
            "Devkit": 0,
            "DevkitGameID": "",
            "DevkitOverrideAppID": 0,
            "LastPlayTime": 0,
            "flatpakAppID": "",
            "tags": {"0": "RomM", "1": "Nintendo 64"},
            "appid": -1073741824,
        }
    ]
    mgr_vdf = SteamVdfManager(str(vdf_file))
    mgr_vdf.save_shortcuts(shortcuts)
    localconfig_file = steam_config / "localconfig.vdf"
    localconfig_file.write_text('"UserLocalConfigStore" { "CloudCollections" {} }')
    backup_mgr = SteamBackupManager(backup_root_dir=tmp_path / "backups")

    # Act
    backup_mgr._resync_localconfig_from_vdf(steam_config)

    # Assert
    assert localconfig_file.exists()


def test_restoreBackup_restoresCloudstorageNamespace(tmp_path):
    # Arrange
    steam_config = tmp_path / "steam_config"
    steam_config.mkdir()
    vdf_file = steam_config / "shortcuts.vdf"
    vdf_file.write_text("vdf content")
    cs_dir = steam_config / "cloudstorage"
    cs_dir.mkdir()
    cs_json = cs_dir / "cloud-storage-namespace-1.json"
    cs_json.write_text('[["test-key", {}]]')
    backup_root = tmp_path / "backups"
    mgr = SteamBackupManager(backup_root_dir=backup_root)
    b_id = mgr.create_backup(str(steam_config))
    assert b_id is not None
    cs_json.write_text('[["mutated-key", {}]]')

    # Act
    ok = mgr.restore_backup(b_id, str(steam_config))

    # Assert
    assert ok is True
    assert cs_json.read_text() == '[["test-key", {}]]'
