"""Unit tests for Steam binary shortcuts.vdf parser, serializer, and AppID generation."""

from romm_steam_sync.adapters.steam_vdf import (
    BinaryVdfParser,
    SteamVdfManager,
    generate_app_id,
)


def test_generateAppId_returnsValidIdentifiers():
    # Arrange
    exe = '"C:/Games/launcher.exe"'
    app_name = "Chrono Trigger"

    # Act
    app_id_32, app_id_64, str_app_id = generate_app_id(exe, app_name)

    # Assert
    assert isinstance(app_id_32, int)
    assert isinstance(app_id_64, int)
    assert isinstance(str_app_id, str)
    assert len(str_app_id) > 0


def test_saveAndLoadShortcuts_roundtrip_preservesData(tmp_path):
    # Arrange
    shortcuts = [
        {
            "AppName": "Super Mario 64",
            "Exe": '"C:/Games/launcher.exe"',
            "StartDir": '"C:/Games/"',
            "icon": "C:/Games/icon.png",
            "ShortcutPath": "",
            "LaunchOptions": "--rom-id 42",
            "IsHidden": 0,
            "AllowDesktopConfig": 1,
            "AllowOverlay": 1,
            "OpenVR": 0,
            "Devkit": 0,
            "DevkitGameID": "",
            "DevkitOverrideAppID": 0,
            "LastPlayTime": 0,
            "flatpakAppID": "",
            "tags": {"0": "RomM", "1": "N64"},
            "appid": -1073741824,
        }
    ]
    vdf_file = tmp_path / "shortcuts.vdf"
    vdf_mgr = SteamVdfManager(str(vdf_file))

    # Act
    vdf_mgr.save_shortcuts(shortcuts)
    loaded = vdf_mgr.load_shortcuts()

    # Assert
    assert vdf_file.exists()
    assert len(loaded) == 1
    assert loaded[0]["AppName"] == "Super Mario 64"
    assert loaded[0]["LaunchOptions"] == "--rom-id 42"
