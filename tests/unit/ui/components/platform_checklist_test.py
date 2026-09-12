"""Unit tests for PlatformChecklistFrame component."""

from unittest.mock import MagicMock

from romm_steam_sync.ui.components.platform_checklist import PlatformChecklistFrame


def test_selectAndDeselectAll_togglesAllVariables():
    # Arrange
    frame = PlatformChecklistFrame.__new__(PlatformChecklistFrame)
    var1 = MagicMock()
    var2 = MagicMock()
    frame.checkbox_vars = {"nes": var1, "snes": var2}

    # Act 1
    frame.select_all()

    # Assert 1
    var1.set.assert_called_with(True)
    var2.set.assert_called_with(True)

    # Act 2
    frame.deselect_all()

    # Assert 2
    var1.set.assert_called_with(False)
    var2.set.assert_called_with(False)


def test_saveSelections_persistsEnabledPlatforms():
    # Arrange
    frame = PlatformChecklistFrame.__new__(PlatformChecklistFrame)
    var_true = MagicMock()
    var_true.get.return_value = True
    var_false = MagicMock()
    var_false.get.return_value = False
    frame.checkbox_vars = {"snes": var_true, "n64": var_false}
    mock_settings = MagicMock()

    # Act
    saved = frame.save_selections(mock_settings)

    # Assert
    assert saved == ["snes"]
    assert mock_settings.enabled_platforms == ["snes"]
    mock_settings.save.assert_called_once()
