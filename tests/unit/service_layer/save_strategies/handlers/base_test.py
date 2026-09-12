"""Unit tests for BaseMemoryCardHandler interface and sanitize_filename utility."""

import pytest

from romm_steam_sync.service_layer.save_strategies.handlers.base import (
    BaseMemoryCardHandler,
    sanitize_filename,
)


def test_sanitizeFilename_stripsInvalidCharacters():
    # Arrange
    raw_name = "Super: Mario / RPG * (USA) ? <Test> | File"

    # Act
    sanitized = sanitize_filename(raw_name)

    # Assert
    assert sanitized == "Super Mario RPG (USA) Test File"


def test_sanitizeFilename_withEmptyString_returnsEmpty():
    # Arrange & Act
    result = sanitize_filename("")

    # Assert
    assert result == ""


def test_baseMemoryCardHandlerClass_cannotBeInstantiatedDirectly():
    # Arrange & Act & Assert
    with pytest.raises(TypeError):
        BaseMemoryCardHandler()  # type: ignore[abstract]
