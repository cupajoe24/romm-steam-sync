"""Unit tests for dictionary extraction helpers."""

import pytest

from romm_steam_sync.domain.dict_helpers import (
    extract_platform_id,
    extract_rom_id,
)


def test_extract_rom_id():
    """Verify extracting integer ROM ID from various dictionary structures."""
    assert extract_rom_id({}) == 0
    assert extract_rom_id({"id": 42}) == 42
    assert extract_rom_id({"rom_id": 99}) == 99
    assert extract_rom_id({"id": "123"}) == 123
    assert extract_rom_id({"id": "invalid"}) == 0
    assert extract_rom_id({"rom_id": None}) == 0
    assert extract_rom_id(None) == 0


def test_extract_platform_id():
    """Verify extracting platform ID or slug from raw dictionaries."""
    assert extract_platform_id({}) == "default"
    assert extract_platform_id({"platform_id": 5}) == 5
    assert extract_platform_id({"platform_slug": "ps1"}) == "ps1"
    assert extract_platform_id({"platform": {"id": 10, "slug": "snes"}}) == 10
    assert extract_platform_id({"platform": {"slug": "genesis"}}) == "genesis"
    assert extract_platform_id(None) == "default"
