"""Unit tests for BaseSaveStrategy abstract base class."""

import pytest

from romm_steam_sync.service_layer.save_strategies.base import BaseSaveStrategy


def test_baseSaveStrategyClass_cannotBeInstantiatedDirectly():
    # Arrange & Act & Assert
    with pytest.raises(TypeError):
        BaseSaveStrategy()  # type: ignore[abstract]
