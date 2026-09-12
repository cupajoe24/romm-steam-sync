"""Global pytest fixtures and isolation guards for romm-steam-sync test suite.

Ensures that no test ever connects to a live database, writes to live user config
directories, or performs unmocked external network/API requests.
"""

from pathlib import Path
import pytest
import requests


@pytest.fixture(autouse=True)
def isolate_test_environment(tmp_path_factory, monkeypatch):
    """Ensure all unit tests use an isolated temporary config directory and database.

    Intercepts get_default_config_dir, get_default_db_path, and AppSettings.get_settings_file
    across all relevant modules to protect the user's live %APPDATA% directory and SQLite DB.
    """
    test_config_dir = tmp_path_factory.mktemp("romm_isolated_config")
    test_db_path = test_config_dir / "romm_steam_sync.db"
    test_settings_file = test_config_dir / "settings.json"

    monkeypatch.setattr(
        "romm_steam_sync.config.get_default_config_dir",
        lambda: test_config_dir,
    )
    monkeypatch.setattr(
        "romm_steam_sync.service_layer.db_session.get_default_db_path",
        lambda: test_db_path,
        raising=False,
    )
    monkeypatch.setattr(
        "romm_steam_sync.service_layer.db_session.get_default_config_dir",
        lambda: test_config_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "romm_steam_sync.service_layer.save_strategies.shared_memory_card.get_default_config_dir",
        lambda: test_config_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "romm_steam_sync.service_layer.cleanup_service.get_default_config_dir",
        lambda: test_config_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "romm_steam_sync.logging_config.get_default_config_dir",
        lambda: test_config_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "romm_steam_sync.adapters.steam_backup.get_default_config_dir",
        lambda: test_config_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "romm_steam_sync.adapters.wrapper_installer.get_default_config_dir",
        lambda: test_config_dir,
        raising=False,
    )
    monkeypatch.setattr(
        "romm_steam_sync.config.AppSettings.get_settings_file",
        lambda *args, **kwargs: test_settings_file,
    )


@pytest.fixture(autouse=True)
def guard_network_calls(monkeypatch):
    """Prevent tests from making live network/HTTP calls.

    Any unmocked HTTP request via requests.Session will fail loudly.
    """
    def forbidden_send(*args, **kwargs):
        raise RuntimeError(
            "Forbidden live network request in test suite! "
            f"All API and HTTP requests must be mocked. args={args}, kwargs={kwargs}"
        )

    monkeypatch.setattr(requests.Session, "send", forbidden_send)


def test_network_guard_blocks_unmocked_requests():
    """Verify that unmocked live network requests are strictly intercepted and blocked."""
    with pytest.raises(RuntimeError, match="Forbidden live network request in test suite"):
        requests.get("https://api.steamgriddb.com/v2/test")


def test_environment_isolation_guards_live_data():
    """Verify that default config dir and database paths point to an isolated temp directory."""
    from romm_steam_sync.config import get_default_config_dir, AppSettings
    from romm_steam_sync.service_layer.db_session import get_default_db_path

    cfg_dir = get_default_config_dir()
    db_p = get_default_db_path()
    settings_p = AppSettings.get_settings_file()

    assert "romm_isolated_config" in str(cfg_dir)
    assert "romm_isolated_config" in str(db_p)
    assert "romm_isolated_config" in str(settings_p)

