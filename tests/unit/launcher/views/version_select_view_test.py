"""Unit tests for VersionSelectView component."""

from unittest.mock import MagicMock
import pytest

from romm_steam_sync.launcher.views.version_select_view import VersionSelectView


def test_versionSelectView_buildVersionListCreatesWidgets():
    # Arrange
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f"Tkinter not available in environment: {e}")

    try:
        card = ctk.CTkFrame(root)
        db_session = MagicMock()
        view = VersionSelectView(card_frame=card, db_session=db_session)

        versions = [
            {"id": 101, "name": "Game (USA)", "is_installed": True},
            {"id": 102, "name": "Game (EUR)", "is_installed": False},
        ]

        # Act
        var = view.build_version_list(
            versions=versions,
            current_rom_id=101,
            canonical_name="Game",
        )

        # Assert
        assert var.get() == 101
        assert view.version_frame is not None
        assert view.always_run_cb is not None
        assert view.get_selected_version(999) == 101

        view.cleanup()
        assert view.version_frame is None
        assert view.always_run_cb is None
    finally:
        root.destroy()


def test_versionSelectView_persistsPreferenceWhenChecked():
    # Arrange
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as e:
        pytest.skip(f"Tkinter not available in environment: {e}")

    try:
        card = ctk.CTkFrame(root)
        db_session = MagicMock()
        db = MagicMock()
        db_session.__enter__.return_value = db
        db_session.__exit__.return_value = None

        view = VersionSelectView(card_frame=card, db_session=db_session)
        view.always_run_var = ctk.BooleanVar(value=True)

        # Act
        view.persist_preference_if_checked(
            selected_id=102,
            rom_id=101,
            sibling_group_key="game_group_1",
        )

        # Assert
        db.kv_config.set.assert_any_call("default_version:game_group_1", "102")
        db.kv_config.set.assert_any_call("default_version:101", "102")
        db.commit.assert_called_once()
    finally:
        root.destroy()
