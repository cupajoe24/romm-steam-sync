"""Unit tests for sibling_resolution 1G1R ranking and representative resolution."""

from romm_steam_sync.domain.sibling_resolution import (
    canonical_group_name,
    resolve_group_representative,
)


def test_resolveGroupRepresentative_installedSiblingWins():
    # Arrange
    members = [
        {"id": 1, "name": "Game (USA)"},
        {"id": 2, "name": "Game (Europe)"},
        {"id": 3, "name": "Game (Japan)"},
    ]

    # Act
    rep = resolve_group_representative(members, installed_rom_ids={2})

    # Assert
    assert rep == 2


def test_resolveGroupRepresentative_boundSiblingWinsOverUnbound():
    # Arrange
    members = [
        {"id": 1, "name": "Game (USA)"},
        {"id": 2, "name": "Game (Europe)"},
    ]

    # Act
    rep = resolve_group_representative(members, bound_rom_ids={2})

    # Assert
    assert rep == 2


def test_resolveGroupRepresentative_mainSiblingWinsWhenUninstalledUnbound():
    # Arrange
    members = [
        {"id": 1, "name": "Game (USA)"},
        {"id": 2, "name": "Game (Europe)", "is_main_sibling": True},
    ]

    # Act
    rep = resolve_group_representative(members)

    # Assert
    assert rep == 2


def test_resolveGroupRepresentative_regionPriorityRanksUsaOverEuropeOverJapan():
    # Arrange
    members = [
        {"id": 3, "name": "Game (Japan)"},
        {"id": 2, "name": "Game (Europe)"},
        {"id": 1, "name": "Game (USA)"},
    ]

    # Act
    rep = resolve_group_representative(members)

    # Assert
    assert rep == 1


def test_resolveGroupRepresentative_prereleaseDemotedBelowRetailAcrossRegions():
    # Arrange
    members = [
        {"id": 1, "name": "Game (USA) (Beta)"},
        {"id": 2, "name": "Game (Japan)"},
    ]

    # Act
    rep = resolve_group_representative(members)

    # Assert
    assert rep == 2


def test_resolveGroupRepresentative_newestRevisionWins():
    # Arrange
    members = [
        {"id": 1, "name": "Game (USA)"},
        {"id": 2, "name": "Game (USA) (Rev 1)", "revision": "Rev 1"},
        {"id": 3, "name": "Game (USA) (Rev 2)", "revision": "Rev 2"},
    ]

    # Act
    rep = resolve_group_representative(members)

    # Assert
    assert rep == 3


def test_canonicalGroupName_extractsBaseTitle():
    # Arrange
    members = [
        {"id": 1, "name": "Final Fantasy VII (USA) (Disc 1)"},
        {"id": 2, "name": "Final Fantasy VII (USA) (Disc 2)"},
    ]

    # Act
    name = canonical_group_name(members)

    # Assert
    assert "Final Fantasy VII" in name
