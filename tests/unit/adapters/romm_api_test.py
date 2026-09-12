"""Unit tests for RomMApiClient API requests, authentication, and save management."""

from unittest.mock import MagicMock, patch
import pytest
import requests

from romm_steam_sync.adapters.romm_api import RomMApiClient, RomMTimeoutError


def test_getRoms_withPlatformId_returnsPaginatedRoms():
    # Arrange
    client = RomMApiClient(base_url="http://mock-romm:8080")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [
            {"id": 10, "name": "Shadow of the Colossus", "platform_id": 12, "platform_slug": "ps2"},
            {"id": 11, "name": "God of War", "platform_id": 12, "platform_slug": "ps2"},
        ],
        "total": 2,
        "limit": 100,
        "offset": 0,
    }
    client.session.get = MagicMock(return_value=mock_response)

    # Act
    roms = client.get_roms(platform_id=12, platform_slug="ps2")

    # Assert
    assert len(roms) == 2
    assert roms[0]["name"] == "Shadow of the Colossus"
    args, kwargs = client.session.get.call_args
    assert kwargs["params"]["platform_ids"] == 12
    assert kwargs["params"]["limit"] == 100
    assert kwargs["params"]["offset"] == 0


def test_ingestPlaySessions_postsPayloadAndReturnsStatus():
    # Arrange
    client = RomMApiClient(base_url="http://mock-romm:8080")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "ok"}'
    mock_response.json.return_value = {"status": "ok"}
    client.session.post = MagicMock(return_value=mock_response)
    sessions = [
        {
            "rom_id": 7905,
            "start_time": "2026-08-29T21:45:08Z",
            "end_time": "2026-08-29T21:46:03Z",
            "duration_ms": 55000,
        }
    ]

    # Act
    res = client.ingest_play_sessions(device_id="test-device-uuid", sessions=sessions)

    # Assert
    assert res == {"status": "ok"}
    client.session.post.assert_called_once()
    args, kwargs = client.session.post.call_args
    assert "api/play-sessions" in args[0]
    assert kwargs["json"]["device_id"] == "test-device-uuid"
    assert len(kwargs["json"]["sessions"]) == 1
    assert kwargs["json"]["sessions"][0]["rom_id"] == 7905


def test_requestWithRetry_succeedsAfterInitialTimeout():
    # Arrange
    client = RomMApiClient(base_url="http://mock-romm:5500")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"id": 1, "name": "SNES"}]

    with patch.object(client.session, "request", side_effect=[
        requests.exceptions.Timeout("Timeout 1"),
        requests.exceptions.Timeout("Timeout 2"),
        mock_resp,
    ]) as mock_req:
        # Act
        resp = client._request_with_retry("GET", "http://mock-romm:5500/api/platforms", retries=3, backoff=0.01)

        # Assert
        assert resp.status_code == 200
        assert mock_req.call_count == 3


def test_requestWithRetry_exceedingRetries_raisesTimeoutError():
    # Arrange
    client = RomMApiClient(base_url="http://mock-romm:5500")

    # Act & Assert
    with patch.object(client.session, "request", side_effect=requests.exceptions.Timeout("Connection timed out")):
        with pytest.raises(RomMTimeoutError) as exc_info:
            client._request_with_retry("GET", "http://mock-romm:5500/api/platforms", retries=3, backoff=0.01)

        assert "timed out after 3 attempts" in str(exc_info.value)


def test_getSaves_returnsRemoteSaveEntries():
    # Arrange
    client = RomMApiClient("http://romm.example.com", api_key="test_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"id": 1, "name": "save.srm"}]

    with patch.object(client.session, "get", return_value=mock_resp):
        # Act
        saves = client.get_saves(123)

        # Assert
        assert len(saves) == 1
        assert saves[0]["id"] == 1


def test_downloadSaveContent_writesBinaryToTargetPath(tmp_path):
    # Arrange
    client = RomMApiClient("http://romm.example.com", api_key="test_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"binary ", b"save ", b"data"]
    target_file = tmp_path / "test.srm"

    with patch.object(client.session, "get", return_value=mock_resp):
        # Act
        res = client.download_save_content(1, str(target_file))

        # Assert
        assert res is True
        assert target_file.read_bytes() == b"binary save data"


def test_uploadSave_postsMultipartFileAndReturnsSaveData(tmp_path):
    # Arrange
    client = RomMApiClient("http://romm.example.com", api_key="test_token")
    save_file = tmp_path / "local.srm"
    save_file.write_bytes(b"local save bytes")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"id": 99, "name": "local.srm"}

    with patch.object(client.session, "post", return_value=mock_resp) as mock_post:
        # Act
        res = client.upload_save(rom_id=123, file_path=str(save_file))

        # Assert
        assert res["id"] == 99
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert "saveFile" in call_kwargs.get("files", {})


def test_authenticate_withApiKey_setsBearerToken():
    # Arrange
    client = RomMApiClient("http://romm.example.com", api_key="my_api_key")
    mock_me_resp = MagicMock()
    mock_me_resp.status_code = 200
    mock_saves_resp = MagicMock()
    mock_saves_resp.status_code = 200
    mock_saves_resp.json.return_value = [{"id": 5}]

    def fake_get(url, **kwargs):
        return mock_me_resp if "users/me" in url else mock_saves_resp

    with patch.object(client.session, "get", side_effect=fake_get):
        # Act
        ok, msg = client.authenticate()
        saves = client.get_saves(123)

        # Assert
        assert ok is True
        assert "API key" in msg
        assert client.session.headers.get("Authorization") == "Bearer my_api_key"
        assert len(saves) == 1


def test_getRomDetail_returnsMetadata():
    # Arrange
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": 42,
        "name": "Super Mario World",
        "platform_slug": "snes",
        "filesize": 524288,
        "filename": "smw.sfc",
    }
    client = RomMApiClient("http://localhost:8080")
    client.session.get = MagicMock(return_value=mock_resp)

    # Act
    detail = client.get_rom_detail(42)

    # Assert
    assert detail["id"] == 42
    assert detail["name"] == "Super Mario World"
    assert detail["filesize"] == 524288


def test_downloadRomContent_streamsBytesToFile(tmp_path):
    # Arrange
    rom_bytes = b"\x00\x01\x02\x03" * 1024
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": str(len(rom_bytes))}
    mock_resp.iter_content.return_value = [rom_bytes]

    client = RomMApiClient("http://localhost:8080")
    client.session.get = MagicMock(return_value=mock_resp)
    target_file = tmp_path / "snes" / "smw.sfc"
    progress_calls = []

    def on_progress(dl, total):
        progress_calls.append((dl, total))

    # Act
    ok = client.download_rom_content(42, str(target_file), progress_callback=on_progress)

    # Assert
    assert ok is True
    assert target_file.exists()
    assert target_file.read_bytes() == rom_bytes
    assert len(progress_calls) > 0
    assert progress_calls[-1][0] == len(rom_bytes)


def test_getRomFileSize_returnsContentLength():
    # Arrange
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-length": "10485760"}
    client = RomMApiClient("http://localhost:8080")
    client.session.head = MagicMock(return_value=mock_resp)

    # Act
    size = client.get_rom_file_size(42, "game.iso")

    # Assert
    assert size == 10485760


def test_downloadCover_withRelativeUrl_prependsBaseUrl(tmp_path):
    # Arrange
    client = RomMApiClient("http://localhost:8080")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"fake_cover_png_data"]
    client.session.request = MagicMock(return_value=mock_resp)

    target_file = tmp_path / "cover.png"

    # Act
    result = client.download_cover(
        rom_id=42,
        target_path=str(target_file),
        cover_url="/api/assets/roms/42/cover.png",
    )

    # Assert
    assert result is True
    assert target_file.read_bytes() == b"fake_cover_png_data"
    args, kwargs = client.session.request.call_args
    assert args[1] == "http://localhost:8080/api/assets/roms/42/cover.png"


def test_downloadCover_withoutCoverUrl_queriesRomDetail(tmp_path):
    # Arrange
    client = RomMApiClient("http://localhost:8080")
    client.get_rom_detail = MagicMock(return_value={
        "id": 42,
        "path_cover_large": "/assets/covers/42_large.png",
    })
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"cover_from_detail"]
    client.session.request = MagicMock(return_value=mock_resp)

    target_file = tmp_path / "cover2.png"

    # Act
    result = client.download_cover(
        rom_id=42,
        target_path=str(target_file),
        cover_url=None,
    )

    # Assert
    assert result is True
    assert target_file.read_bytes() == b"cover_from_detail"
    client.get_rom_detail.assert_called_once_with(42)
    args, kwargs = client.session.request.call_args
    assert args[1] == "http://localhost:8080/assets/covers/42_large.png"


def test_downloadCover_whenEndpointReturns404_returnsFalse(tmp_path):
    # Arrange
    client = RomMApiClient("http://localhost:8080")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    client.session.request = MagicMock(return_value=mock_resp)

    target_file = tmp_path / "not_found.png"

    # Act
    result = client.download_cover(
        rom_id=999,
        target_path=str(target_file),
        cover_url="http://localhost:8080/api/roms/999/cover",
    )

    # Assert
    assert result is False
    assert not target_file.exists()
