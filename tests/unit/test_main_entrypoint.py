"""Unit tests for __main__.py application entry point."""

import sys
from unittest.mock import patch

from romm_steam_sync.__main__ import main


def test_main_whenRomIdPresent_invokesLauncherMain(monkeypatch):
    """Verify that --rom-id argument routes execution to launcher_main."""
    monkeypatch.setattr(sys, "argv", ["romm-steam-sync", "--rom-id", "42"])
    with patch("romm_steam_sync.launcher.__main__.main") as mock_launcher, patch(
        "romm_steam_sync.ui.app.main"
    ) as mock_ui:
        main()
        mock_launcher.assert_called_once()
        mock_ui.assert_not_called()


def test_main_whenNoRomId_invokesUiMain(monkeypatch):
    """Verify that default execution without --rom-id routes to ui_main."""
    monkeypatch.setattr(sys, "argv", ["romm-steam-sync"])
    with patch("romm_steam_sync.launcher.__main__.main") as mock_launcher, patch(
        "romm_steam_sync.ui.app.main"
    ) as mock_ui:
        main()
        mock_ui.assert_called_once()
        mock_launcher.assert_not_called()
