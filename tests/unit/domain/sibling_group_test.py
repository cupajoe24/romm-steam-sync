"""Unit tests for sibling_group connected component key derivation."""

from romm_steam_sync.domain.sibling_group import (
    compute_component_group_keys,
    compute_sibling_group_key,
    target_in_sibling_group,
)


def test_computeSiblingGroupKey_coalescesIgdbFirst():
    # Arrange
    rom = {
        "id": 1,
        "platform_slug": "ps1",
        "igdb_id": 101,
        "ss_id": 202,
        "ra_id": 303,
    }

    # Act
    key = compute_sibling_group_key(rom)

    # Assert
    assert key == "igdb:101:ps1"


def test_computeSiblingGroupKey_coalescesScreenscraperWhenIgdbAbsent():
    # Arrange
    rom = {
        "id": 2,
        "platform_slug": "ps1",
        "ss_id": 202,
        "ra_id": 303,
    }

    # Act
    key = compute_sibling_group_key(rom)

    # Assert
    assert key == "ss:202:ps1"


def test_computeSiblingGroupKey_scopesByPlatformSlug():
    # Arrange
    rom1 = {"id": 1, "platform_slug": "ps1", "igdb_id": 101}
    rom2 = {"id": 1, "platform_slug": "ps2", "igdb_id": 101}

    # Act
    key1 = compute_sibling_group_key(rom1)
    key2 = compute_sibling_group_key(rom2)

    # Assert
    assert key1 == "igdb:101:ps1"
    assert key2 == "igdb:101:ps2"
    assert key1 != key2


def test_computeSiblingGroupKey_fallsBackToRommId():
    # Arrange
    rom = {"id": 99, "platform_slug": "snes"}

    # Act
    key = compute_sibling_group_key(rom)

    # Assert
    assert key == "romm:99:snes"


def test_computeComponentGroupKeys_clustersConnectedSiblings():
    # Arrange
    unit_roms = [
        {"id": 1, "platform_slug": "ps1", "igdb_id": 500, "sibling_roms": [{"id": 2}, {"id": 3}]},
        {"id": 2, "platform_slug": "ps1", "sibling_roms": [{"id": 1}]},
        {"id": 3, "platform_slug": "ps1", "sibling_roms": [{"id": 1}]},
        {"id": 4, "platform_slug": "ps1"},
    ]

    # Act
    keys = compute_component_group_keys(unit_roms)

    # Assert
    assert keys[1] == "igdb:500:ps1"
    assert keys[2] == "igdb:500:ps1"
    assert keys[3] == "igdb:500:ps1"
    assert keys[4] == "romm:4:ps1"


def test_targetInSiblingGroup_evaluatesGroupInclusion():
    # Arrange & Act
    is_in_group = target_in_sibling_group(
        bound_group_key="igdb:500:ps1",
        target_group_key="igdb:500:ps1",
        target_is_local=True,
    )
    is_different_group = target_in_sibling_group(
        bound_group_key="igdb:500:ps1",
        target_group_key="igdb:999:ps1",
        target_is_local=True,
    )

    # Assert
    assert is_in_group is True
    assert is_different_group is False
