"""Unit tests for application configuration and settings models."""

from pathlib import Path
import tempfile
from unittest.mock import patch

from romm_steam_sync.config import AppSettings, get_default_config_dir


def test_appSettingsClass_defaultInitialization_setsExpectedDefaults():
    # Arrange & Act
    settings = AppSettings()

    # Assert
    assert settings.onboarding_complete is False
    assert settings.romm_url == "http://"
    assert settings.steam_user_id == "auto"
    assert settings.default_slot == "autosave"
    assert settings.save_sync_enabled is True
    assert settings.enabled_platforms == []
    assert settings.core_mappings == {}


def test_saveAndLoad_roundtrip_persistsSettings():
    # Arrange
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        settings_file = tmp_path / "settings.json"

        with patch("romm_steam_sync.config.get_default_config_dir", return_value=tmp_path):
            settings = AppSettings(
                romm_url="https://romm.example.com",
                api_key="testapikey",
                onboarding_complete=True,
                save_sync_enabled=False,
                enabled_platforms=["snes", "gba"],
            )

            # Act
            settings.save()
            loaded = AppSettings.load()

            # Assert
            assert AppSettings.get_settings_file().exists()
            assert loaded.romm_url == "https://romm.example.com"
            assert loaded.api_key == "testapikey"
            assert loaded.onboarding_complete is True
            assert loaded.save_sync_enabled is False
            assert loaded.enabled_platforms == ["snes", "gba"]


def test_setCoreOverride_updatesAndClears():
    # Arrange
    settings = AppSettings()

    # Act
    settings.set_core_override("snes", "snes9x_libretro")
    settings.set_core_override("gba", "mgba_libretro")
    snes_core = settings.get_core_override("snes")
    settings.remove_core_override("snes")
    snes_after_remove = settings.get_core_override("snes")
    settings.clear_all_core_overrides()

    # Assert
    assert snes_core == "snes9x_libretro"
    assert snes_after_remove is None
    assert settings.core_mappings == {}


def test_getDefaultConfigDir_returnsValidPath():
    # Arrange & Act
    config_dir = get_default_config_dir()

    # Assert
    assert isinstance(config_dir, Path)
    assert config_dir.exists()
