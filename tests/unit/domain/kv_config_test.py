"""Unit tests for KvConfig domain model."""

from romm_steam_sync.domain.kv_config import KvConfig


def test_kvConfigClass_initialization_setsKeyAndValue():
    # Arrange & Act
    kv = KvConfig(key="last_sync", value="2026-09-01T00:00:00Z")

    # Assert
    assert kv.key == "last_sync"
    assert kv.value == "2026-09-01T00:00:00Z"
    assert kv.updated_at is None
