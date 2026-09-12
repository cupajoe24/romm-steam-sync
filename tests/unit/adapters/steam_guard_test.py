"""Unit tests for Steam process inspection guard."""

from unittest.mock import patch

from romm_steam_sync.adapters.steam_guard import SteamGuard


def test_isSteamRunning_returnsBoolean():
    # Arrange & Act
    is_running = SteamGuard.is_steam_running()

    # Assert
    assert isinstance(is_running, bool)


def test_getRunningSteamProcesses_returnsList():
    # Arrange & Act
    running_procs = SteamGuard.get_running_steam_processes()

    # Assert
    assert isinstance(running_procs, list)


def test_isSteamRunning_whenMocked_returnsMockedState():
    # Arrange
    with patch("romm_steam_sync.adapters.steam_guard.SteamGuard.is_steam_running", return_value=True):
        # Act
        running = SteamGuard.is_steam_running()

        # Assert
        assert running is True


def test_isSteamRunning_detectsMacOsSteamOsx():
    from unittest.mock import MagicMock
    fake_proc = MagicMock()
    fake_proc.info = {"name": "steam_osx"}

    with patch("psutil.process_iter", return_value=[fake_proc]):
        assert SteamGuard.is_steam_running() is True
        assert SteamGuard.get_running_steam_processes() == ["steam_osx"]


def test_isSteamRunning_detectsLinuxSteamScript():
    from unittest.mock import MagicMock
    fake_proc = MagicMock()
    fake_proc.info = {"name": "steam.sh"}

    with patch("psutil.process_iter", return_value=[fake_proc]):
        assert SteamGuard.is_steam_running() is True
        assert SteamGuard.get_running_steam_processes() == ["steam.sh"]

