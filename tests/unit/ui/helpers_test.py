"""Unit tests for UI helper routines and validation utilities."""

from unittest.mock import MagicMock, patch

from romm_steam_sync.config import AppSettings
import romm_steam_sync.ui.helpers as ui_helpers


def test_testAndSaveRommCredentials_authenticatesAndSavesSettings():
    # Arrange
    settings = AppSettings()
    mock_client_cls = MagicMock()
    mock_client = mock_client_cls.return_value
    mock_client.authenticate.return_value = (True, "Connection OK")

    with patch("romm_steam_sync.ui.helpers.install_wrapper") as mock_install:
        # Act
        ok, msg = ui_helpers.test_and_save_romm_credentials(
            settings=settings,
            url="http://romm.example:8080",
            api_key="token123",
            client_cls=mock_client_cls,
            install_launcher=True,
        )

        # Assert
        assert ok is True
        assert msg == "Connection OK"
        assert settings.romm_url == "http://romm.example:8080"
        assert settings.api_key == "token123"
        mock_install.assert_called_once()


def test_testAndSaveRommCredentials_withEmptyUrl_returnsError():
    # Arrange
    settings = AppSettings()

    # Act: blank whitespace URL
    ok, msg = ui_helpers.test_and_save_romm_credentials(
        settings=settings,
        url="   ",
        api_key="",
    )

    # Assert
    assert ok is False
    assert "RomM Server URL is required" in msg

    # Act: scheme-only default placeholder
    ok2, msg2 = ui_helpers.test_and_save_romm_credentials(
        settings=settings,
        url="http://",
        api_key="",
    )

    # Assert
    assert ok2 is False
    assert "RomM Server URL is required" in msg2


def test_verifySteamgriddbKey_handlesEmptyValidAndInvalidKeys():
    # Arrange & Act 1: Empty key
    ok_empty, msg_empty = ui_helpers.verify_steamgriddb_key("  ")

    # Assert 1
    assert ok_empty is False
    assert "Please enter an API Key" in msg_empty

    # Arrange & Act 2: Valid key
    mock_client_cls = MagicMock()
    mock_client = mock_client_cls.return_value
    mock_client.verify_api_key.return_value = (True, "Key is valid")
    ok_val, msg_val = ui_helpers.verify_steamgriddb_key("valid_key", client_cls=mock_client_cls)

    # Assert 2
    assert ok_val is True
    assert msg_val == "Key is valid"

    # Arrange & Act 3: Invalid key
    mock_client.verify_api_key.return_value = (False, "Unauthorized")
    ok_inval, msg_inval = ui_helpers.verify_steamgriddb_key("invalid_key", client_cls=mock_client_cls)

    # Assert 3
    assert ok_inval is False
    assert msg_inval == "Unauthorized"


def test_browseRetroarchExecutable_invokesFileDialog():
    # Arrange
    with patch("romm_steam_sync.ui.helpers.filedialog.askopenfilename", return_value="/path/to/retroarch.exe") as mock_dialog:
        # Act
        chosen = ui_helpers.browse_retroarch_executable()

        # Assert
        assert chosen == "/path/to/retroarch.exe"
        assert mock_dialog.called


def test_resetProgressBar_configuresModeAndSetsValue():
    # Arrange
    pb = MagicMock()

    # Act
    ui_helpers.reset_progress_bar(pb, mode="determinate", value=0.5)

    # Assert
    pb.stop.assert_called_once()
    pb.configure.assert_called_with(mode="determinate")
    pb.set.assert_called_with(0.5)
