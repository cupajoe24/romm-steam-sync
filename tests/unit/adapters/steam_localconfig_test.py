"""Unit tests for SteamLocalConfigManager collections synchronization."""

import json
from pathlib import Path
import vdf

from romm_steam_sync.adapters.steam_localconfig import SteamLocalConfigManager


def test_updateCollections_updatesVdfAndCloudstorage(tmp_path):
    # Arrange
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    localconfig_vdf = config_dir / "localconfig.vdf"
    initial_vdf = {
        "UserLocalConfigStore": {
            "CloudCollections": {
                "user-collection-romm--playstation-2": {
                    "id": "user-collection-romm--playstation-2",
                    "name": "RomM: PlayStation 2",
                    "added": "[11111]",
                    "removed": "[]",
                }
            }
        }
    }
    with open(localconfig_vdf, "w", encoding="utf-8") as f:
        vdf.dump(initial_vdf, f)
    mgr = SteamLocalConfigManager(str(config_dir))
    platform_app_ids = {
        "PlayStation 2": {11831270853260083200, 9244494750474567680},
        "Dreamcast": {9453250128363126784},
    }
    master_app_ids = {11831270853260083200, 9244494750474567680, 9453250128363126784}

    # Act
    ok = mgr.update_collections(platform_app_ids, master_app_ids)

    # Assert
    assert ok is True
    with open(localconfig_vdf, "r", encoding="utf-8") as f:
        updated = vdf.load(f)
    cloud_cols = updated.get("UserLocalConfigStore", {}).get("CloudCollections", {})
    assert "user-collection-romm--playstation-2" not in cloud_cols
    assert "user-collection-playstation-2" in cloud_cols
    assert "user-collection-dreamcast" in cloud_cols
    assert "user-collection-romm" in cloud_cols
    ps2_added = json.loads(cloud_cols["user-collection-playstation-2"]["added"])
    assert 11831270853260083200 in ps2_added
    assert 9244494750474567680 in ps2_added

    json_path = config_dir / "cloudstorage" / "cloud-storage-namespace-1.json"
    ns_ver_path = config_dir / "cloudstorage" / "cloud-storage-namespaces.json"
    assert json_path.exists()
    assert ns_ver_path.exists()
    with open(json_path, "r", encoding="utf-8") as f:
        cloud_items = json.load(f)
    cloud_map = {item[0]: item[1] for item in cloud_items if isinstance(item, list) and len(item) == 2}
    assert "user-collections.user-collection-playstation-2" in cloud_map
    assert "user-collections.user-collection-dreamcast" in cloud_map
    assert "user-collections.user-collection-romm" in cloud_map


def test_removeCollection_removesPlatformFromVdf(tmp_path):
    # Arrange
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    localconfig_vdf = config_dir / "localconfig.vdf"
    with open(localconfig_vdf, "w", encoding="utf-8") as f:
        vdf.dump({"UserLocalConfigStore": {"CloudCollections": {}}}, f)
    mgr = SteamLocalConfigManager(str(config_dir))
    platform_app_ids = {
        "PlayStation 2": {11831270853260083200},
        "Dreamcast": {9453250128363126784},
    }
    master_app_ids = {11831270853260083200, 9453250128363126784}
    mgr.update_collections(platform_app_ids, master_app_ids)

    # Act
    ok = mgr.remove_collection("PlayStation 2", {11831270853260083200})

    # Assert
    assert ok is True
    with open(localconfig_vdf, "r", encoding="utf-8") as f:
        updated = vdf.load(f)
    cloud_cols = updated.get("UserLocalConfigStore", {}).get("CloudCollections", {})
    assert "user-collection-playstation-2" not in cloud_cols
    assert "user-collection-dreamcast" in cloud_cols
    romm_added = json.loads(cloud_cols["user-collection-romm"]["added"])
    assert 11831270853260083200 not in romm_added
    assert 9453250128363126784 in romm_added


def test_removeAllRommCollections_clearsAllRommGroups(tmp_path):
    # Arrange
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    localconfig_vdf = config_dir / "localconfig.vdf"
    with open(localconfig_vdf, "w", encoding="utf-8") as f:
        vdf.dump({"UserLocalConfigStore": {"CloudCollections": {}}}, f)
    mgr = SteamLocalConfigManager(str(config_dir))
    platform_app_ids = {
        "PlayStation 2": {11831270853260083200},
    }
    master_app_ids = {11831270853260083200}
    mgr.update_collections(platform_app_ids, master_app_ids)

    # Act
    ok = mgr.remove_all_romm_collections()

    # Assert
    assert ok is True
    with open(localconfig_vdf, "r", encoding="utf-8") as f:
        updated = vdf.load(f)
    cloud_cols = updated.get("UserLocalConfigStore", {}).get("CloudCollections", {})
    assert "user-collection-playstation-2" not in cloud_cols
    assert "user-collection-romm" not in cloud_cols
