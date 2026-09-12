"""Unit tests for PlatformSyncDiff and SyncDiff domain models."""

from romm_steam_sync.domain.rom import Rom
from romm_steam_sync.domain.sync_diff import PlatformSyncDiff, SyncDiff


def test_platformSyncDiffClass_counts_calculatesCorrectTotals():
    # Arrange
    rom_rem = Rom(rom_id=1, platform_slug="snes", name="Old Game")
    p_diff = PlatformSyncDiff(
        platform_slug="snes",
        platform_name="Super Nintendo",
        additions=[{"id": 2, "name": "New Game"}],
        removals_roms=[rom_rem],
        removals_shortcuts=[{"appid": 1234}],
        unchanged_roms=[{"id": 3, "name": "Existing Game"}],
    )

    # Act & Assert
    assert p_diff.additions_count == 1
    assert p_diff.removals_count == 2
    assert p_diff.unchanged_count == 1


def test_syncDiffClass_aggregatedProperties_sumsAcrossAllPlatforms():
    # Arrange
    snes_diff = PlatformSyncDiff(
        platform_slug="snes",
        platform_name="Super Nintendo",
        additions=[{"id": 1}],
        removals_roms=[Rom(rom_id=2, platform_slug="snes", name="Old")],
        unchanged_roms=[{"id": 3}, {"id": 4}],
    )
    gba_diff = PlatformSyncDiff(
        platform_slug="gba",
        platform_name="Game Boy Advance",
        additions=[{"id": 5}, {"id": 6}],
        removals_roms=[],
        unchanged_roms=[{"id": 7}],
    )
    sync_diff = SyncDiff(platform_diffs={"snes": snes_diff, "gba": gba_diff})

    # Act & Assert
    assert sync_diff.total_additions == 3
    assert sync_diff.total_removals == 1
    assert sync_diff.total_unchanged == 3
