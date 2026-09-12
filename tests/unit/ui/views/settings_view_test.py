"""Unit tests for SettingsView configuration and core mapping UI."""

from pathlib import Path
from unittest.mock import patch
import customtkinter as ctk
import pytest

from romm_steam_sync.config import AppSettings
from romm_steam_sync.ui.views.settings_view import SettingsView


def test_coreMappings_updatesAndPersists(tmp_path):
    # Arrange
    try:
        root = ctk.CTk()
        root.withdraw()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        settings_file = tmp_path / "settings.json"
        with patch.object(AppSettings, "get_settings_file", return_value=settings_file):
            settings = AppSettings()
            settings.set_core_override("snes", "bsnes_libretro")
            view = SettingsView(root, settings)

            # Act 1: Verify initial population
            assert "snes" in view.platform_core_widgets
            assert "nes" in view.platform_core_widgets
            _, snes_combo, snes_default = view.platform_core_widgets["snes"]
            assert snes_default == "snes9x_libretro"
            assert snes_combo.get() == "bsnes_libretro"

            # Act 2: Modify a combobox and save
            _, nes_combo, _ = view.platform_core_widgets["nes"]
            nes_combo.set("fceumm_libretro")
            view.save_core_mappings()

            # Assert 2
            assert view.settings.get_core_override("nes") == "fceumm_libretro"

            # Act 3: Reset single core
            view._reset_core("nes")

            # Assert 3
            assert "nestopia_libretro" in nes_combo.get()

            # Act 4: Filter core rows
            view.core_filter_entry.insert(0, "snes")
            view._filter_core_rows()

            # Act 5: Add custom mapping
            view.custom_slug_entry.insert(0, "satellaview")
            view.custom_core_entry.insert(0, "snes9x_libretro")
            view._add_custom_core_mapping()

            # Assert 5
            assert "satellaview" in view.platform_core_widgets
            assert view.settings.get_core_override("satellaview") == "snes9x_libretro"

            # Act 6: Reset all cores to defaults
            view._reset_all_cores()
            view.save_core_mappings()

            # Assert 6
            assert len(view.settings.core_mappings) == 0

            # Act 7: Test save_preferences
            view.save_preferences()

            # Assert 7
            assert "Preferences saved" in view.pref_status_label.cget("text")
    finally:
        root.destroy()


def test_settingsView_displaysVersionInUpperRight(tmp_path):
    """Verify SettingsView displays the application version in the upper right."""
    try:
        root = ctk.CTk()
        root.withdraw()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        settings_file = tmp_path / "settings.json"
        with patch.object(AppSettings, "get_settings_file", return_value=settings_file), \
             patch("romm_steam_sync.ui.views.settings_view.__version__", "9.9.9"):
            settings = AppSettings()
            view = SettingsView(root, settings)

            assert hasattr(view, "version_label")
            assert view.version_label.cget("text") == "v9.9.9"
            grid_info = view.version_label.grid_info()
            assert int(grid_info["row"]) == 0
            assert int(grid_info["column"]) == 0
            assert "e" in grid_info["sticky"]
    finally:
        root.destroy()


def test_saveSyncSwitch_togglesAndPersistsPreference(tmp_path):
    """Verify Save Syncing switch initializes correctly and persists preference when saved."""
    try:
        root = ctk.CTk()
        root.withdraw()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        settings_file = tmp_path / "settings.json"
        with patch.object(AppSettings, "get_settings_file", return_value=settings_file):
            # Arrange - enabled by default
            settings = AppSettings(save_sync_enabled=True)
            view = SettingsView(root, settings)

            # Assert switch exists and is placed above default save slot
            assert hasattr(view, "save_sync_switch")
            switch_grid = view.save_sync_switch.grid_info()
            slot_grid = view.slot_entry.grid_info()
            assert int(switch_grid["row"]) < int(slot_grid["row"])
            assert view.save_sync_switch.get() == 1

            # Act: Deselect and save preferences
            view.save_sync_switch.deselect()
            view.save_preferences()

            # Assert: Settings updated to False
            assert view.settings.save_sync_enabled is False

            # Arrange: Re-create view with disabled settings
            view2 = SettingsView(root, view.settings)

            # Assert: Switch initialized as deselected
            assert view2.save_sync_switch.get() == 0
    finally:
        root.destroy()


