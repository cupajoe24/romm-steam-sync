"""Unit tests for BaseChoiceModal, CancelSyncModal, and TimeoutResolutionModal."""

from unittest.mock import MagicMock

from romm_steam_sync.ui.components.base_choice_modal import BaseChoiceModal
from romm_steam_sync.ui.components.cancel_modal import SyncCancelModal
from romm_steam_sync.ui.components.timeout_modal import RomMTimeoutModal


def test_baseChoiceModal_selectTriggersCallbackAndDestroys() -> None:
    modal = BaseChoiceModal.__new__(BaseChoiceModal)
    mock_destroy = MagicMock()
    modal.destroy = mock_destroy
    on_choice = MagicMock()
    modal.on_choice = on_choice

    modal._select("confirmed_action")

    assert modal.selected_choice == "confirmed_action"
    mock_destroy.assert_called_once()
    on_choice.assert_called_once_with("confirmed_action")


def test_baseChoiceModal_selectWithNoCallback_destroysCleanly() -> None:
    modal = BaseChoiceModal.__new__(BaseChoiceModal)
    mock_destroy = MagicMock()
    modal.destroy = mock_destroy
    modal.on_choice = None

    modal._select("dismiss")

    assert modal.selected_choice == "dismiss"
    mock_destroy.assert_called_once()


def test_syncCancelModal_isSubclassOfBaseChoiceModal() -> None:
    assert issubclass(SyncCancelModal, BaseChoiceModal)


def test_rommTimeoutModal_isSubclassOfBaseChoiceModal() -> None:
    assert issubclass(RomMTimeoutModal, BaseChoiceModal)
