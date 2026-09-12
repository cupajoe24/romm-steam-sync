"""Unit tests for ConfirmationModal and AlertModal."""

from unittest.mock import MagicMock

from romm_steam_sync.ui.components.confirmation_modal import AlertModal, ConfirmationModal


def test_handleConfirm_triggersCallbackAndDestroys():
    # Arrange
    modal = ConfirmationModal.__new__(ConfirmationModal)
    mock_destroy = MagicMock()
    modal.destroy = mock_destroy
    on_confirm = MagicMock()
    modal._on_confirm = on_confirm

    # Act
    modal._handle_confirm()

    # Assert
    mock_destroy.assert_called_once()
    on_confirm.assert_called_once()


def test_handleClose_triggersCallbackAndDestroys():
    # Arrange
    alert = AlertModal.__new__(AlertModal)
    mock_destroy = MagicMock()
    alert.destroy = mock_destroy
    on_close = MagicMock()
    alert._on_close = on_close

    # Act
    alert._handle_close()

    # Assert
    mock_destroy.assert_called_once()
    on_close.assert_called_once()
