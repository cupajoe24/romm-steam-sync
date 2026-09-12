"""Unit tests for SteamPathResolver."""

from romm_steam_sync.adapters.steam_path import SteamPathResolver


def test_listUserIds_returnsDetectedUserIds(tmp_path):
    # Arrange
    fake_steam = tmp_path / "Steam"
    userdata = fake_steam / "userdata"
    user_dir = userdata / "12345678"
    user_dir.mkdir(parents=True)

    # Act
    user_ids = SteamPathResolver.list_user_ids(str(fake_steam))

    # Assert
    assert user_ids == ["12345678"]


def test_getUserConfigDir_resolvesConfigPath(tmp_path):
    # Arrange
    fake_steam = tmp_path / "Steam"
    userdata = fake_steam / "userdata"
    user_dir = userdata / "12345678"
    user_dir.mkdir(parents=True)

    # Act
    config_dir, sel_id = SteamPathResolver.get_user_config_dir(user_id="12345678", custom_steam_path=str(fake_steam))

    # Assert
    assert sel_id == "12345678"
    assert config_dir is not None
    assert config_dir.name == "config"


def test_getSteamRoot_linuxDebianInstallation(tmp_path):
    # Arrange
    from unittest.mock import patch
    fake_home = tmp_path / "home"
    debian_steam = fake_home / ".steam" / "debian-installation"
    debian_steam.mkdir(parents=True)

    with patch("romm_steam_sync.adapters.steam_path.sys.platform", "linux"), \
         patch("romm_steam_sync.adapters.steam_path.Path.home", return_value=fake_home):
        # Act
        root = SteamPathResolver.get_steam_root()

        # Assert
        assert root == debian_steam


def test_getSteamRoot_linuxSnapPath(tmp_path):
    # Arrange
    from unittest.mock import patch
    fake_home = tmp_path / "home"
    snap_steam = fake_home / "snap" / "steam" / "common" / ".local" / "share" / "Steam"
    snap_steam.mkdir(parents=True)

    with patch("romm_steam_sync.adapters.steam_path.sys.platform", "linux"), \
         patch("romm_steam_sync.adapters.steam_path.Path.home", return_value=fake_home):
        # Act
        root = SteamPathResolver.get_steam_root()

        # Assert
        assert root == snap_steam


def test_getSteamRoot_macOsPath(tmp_path):
    # Arrange
    from unittest.mock import patch
    fake_home = tmp_path / "home"
    mac_steam = fake_home / "Library" / "Application Support" / "Steam"
    mac_steam.mkdir(parents=True)

    with patch("romm_steam_sync.adapters.steam_path.sys.platform", "darwin"), \
         patch("romm_steam_sync.adapters.steam_path.Path.home", return_value=fake_home):
        # Act
        root = SteamPathResolver.get_steam_root()

        # Assert
        assert root == mac_steam


def test_getLibraryFolders_parsesLibraryFoldersVdf(tmp_path):
    # Arrange
    fake_steam = tmp_path / "Steam"
    fake_steam.mkdir()
    steamapps = fake_steam / "steamapps"
    steamapps.mkdir()

    extra_lib = tmp_path / "ExtraLibrary"
    extra_lib.mkdir()

    vdf_file = steamapps / "libraryfolders.vdf"
    escaped_steam = str(fake_steam).replace("\\", "\\\\")
    escaped_extra = str(extra_lib).replace("\\", "\\\\")
    vdf_file.write_text(f'''
"libraryfolders"
{{
    "0"
    {{
        "path"    "{escaped_steam}"
    }}
    "1"
    {{
        "path"    "{escaped_extra}"
    }}
}}
''', encoding="utf-8")

    # Act
    folders = SteamPathResolver.get_library_folders(custom_steam_path=str(fake_steam))

    # Assert
    resolved_paths = [f.resolve() for f in folders]
    assert fake_steam.resolve() in resolved_paths
    assert extra_lib.resolve() in resolved_paths


def test_getLibraryFolders_handlesMissingVdf(tmp_path):
    # Arrange
    fake_steam = tmp_path / "Steam"
    fake_steam.mkdir()

    # Act
    folders = SteamPathResolver.get_library_folders(custom_steam_path=str(fake_steam))

    # Assert
    assert folders == [fake_steam.resolve()]


