"""Unit tests for SteamGridDbClient REST API adapter."""

from unittest.mock import MagicMock, patch

from romm_steam_sync.adapters.steamgriddb import SGDB_BASE_URL, SteamGridDbClient


def test_verifyApiKey_whenValid_returnsTrue():
    # Arrange
    client = SteamGridDbClient(api_key="test_key_123")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "data": []}

    with patch.object(client.session, "get", return_value=mock_resp) as mock_get:
        # Act
        ok, msg = client.verify_api_key()

        # Assert
        assert ok is True
        assert "valid" in msg.lower()
        mock_get.assert_called_once_with(
            f"{SGDB_BASE_URL}/search/autocomplete/test",
            headers={
                "User-Agent": "romm-steam-sync/1.0",
                "Authorization": "Bearer test_key_123",
            },
            timeout=10,
        )


def test_verifyApiKey_whenInvalid_returnsFalse():
    # Arrange
    client = SteamGridDbClient(api_key="invalid_key")
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch.object(client.session, "get", return_value=mock_resp):
        # Act
        ok, msg = client.verify_api_key()

        # Assert
        assert ok is False
        assert "unauthorized" in msg.lower() or "invalid" in msg.lower()


def test_getGameByIgdbId_returnsGameId():
    # Arrange
    client = SteamGridDbClient(api_key="valid_key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "data": {"id": 4567, "name": "Super Mario World"}}

    with patch.object(client.session, "get", return_value=mock_resp):
        # Act
        game_id = client.get_game_by_igdb_id(1234)

        # Assert
        assert game_id == 4567


def test_searchGameByName_returnsGameId():
    # Arrange
    client = SteamGridDbClient(api_key="valid_key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "data": [{"id": 8888, "name": "Chrono Trigger"}],
    }

    with patch.object(client.session, "get", return_value=mock_resp):
        # Act
        game_id = client.search_game_by_name("Chrono Trigger")

        # Assert
        assert game_id == 8888


def test_searchGame_delegatesToSearchGameByName():
    # Arrange
    client = SteamGridDbClient(api_key="valid_key")

    with patch.object(client, "search_game_by_name", return_value=8888) as mock_search:
        # Act
        game_id = client.search_game("Chrono Trigger")

        # Assert
        assert game_id == 8888
        mock_search.assert_called_once_with("Chrono Trigger")


def test_getAssetUrl_returnsHighestRatedImageUrl():
    # Arrange
    client = SteamGridDbClient(api_key="valid_key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "data": [
            {"id": 1, "score": 10, "url": "https://cdn.steamgriddb.com/hero/top_rated.png"},
            {"id": 2, "score": 2, "url": "https://cdn.steamgriddb.com/hero/lower_rated.png"},
        ],
    }

    with patch.object(client.session, "get", return_value=mock_resp):
        # Act
        url = client.get_asset_url("hero", 8888)

        # Assert
        assert url == "https://cdn.steamgriddb.com/hero/top_rated.png"


def test_downloadImage_writesBinaryStreamToFile(tmp_path):
    # Arrange
    client = SteamGridDbClient(api_key="valid_key")
    target_file = tmp_path / "test_hero.png"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"png_image_data_chunk"]

    with patch.object(client.session, "get", return_value=mock_resp):
        # Act
        res = client.download_image("https://cdn.steamgriddb.com/hero/top.png", str(target_file))

        # Assert
        assert res is True
        assert target_file.exists()
        assert target_file.read_bytes() == b"png_image_data_chunk"
