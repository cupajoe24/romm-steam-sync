"""Unit tests for save strategy registry and core mapping resolution."""

from romm_steam_sync.service_layer.save_strategies.default_save_per_game import (
    DefaultSavePerGameStrategy,
)
from romm_steam_sync.service_layer.save_strategies.memory_card_per_game import (
    MemoryCardPerGameStrategy,
)
from romm_steam_sync.service_layer.save_strategies.registry import (
    CORE_SAVE_STRATEGY_MAP,
    SAVE_STRATEGY_REGISTRY,
    get_save_strategy,
)
from romm_steam_sync.service_layer.save_strategies.shared_memory_card import (
    SharedMemoryCardStrategy,
)


def test_getSaveStrategy_byExplicitName_returnsRegisteredStrategy():
    # Arrange & Act
    default_strat = get_save_strategy(strategy_name="default_save_per_game")
    shared_strat = get_save_strategy(strategy_name="shared_memory_card")
    memcard_strat = get_save_strategy(strategy_name="memory_card_per_game")

    # Assert
    assert isinstance(default_strat, DefaultSavePerGameStrategy)
    assert isinstance(shared_strat, SharedMemoryCardStrategy)
    assert isinstance(memcard_strat, MemoryCardPerGameStrategy)


def test_getSaveStrategy_explicitCoreMappings_resolvesAccurately():
    # Arrange & Act & Assert
    assert isinstance(get_save_strategy(core_name="pcsx2_libretro"), SharedMemoryCardStrategy)
    assert isinstance(get_save_strategy(core_name="lrps2_libretro"), SharedMemoryCardStrategy)
    assert isinstance(get_save_strategy(core_name="flycast_libretro"), SharedMemoryCardStrategy)
    assert isinstance(get_save_strategy(core_name="dolphin_libretro"), MemoryCardPerGameStrategy)
    assert isinstance(get_save_strategy(core_name="citra_libretro"), MemoryCardPerGameStrategy)
    assert isinstance(get_save_strategy(core_name="snes9x_libretro"), DefaultSavePerGameStrategy)


def test_getSaveStrategy_byPlatformSlug_resolvesAccurately():
    # Arrange & Act & Assert
    assert isinstance(get_save_strategy(platform_slug="ps2"), SharedMemoryCardStrategy)
    assert isinstance(get_save_strategy(platform_slug="dreamcast"), SharedMemoryCardStrategy)
    assert isinstance(get_save_strategy(platform_slug="gc"), MemoryCardPerGameStrategy)
    assert isinstance(get_save_strategy(platform_slug="3ds"), MemoryCardPerGameStrategy)
    assert isinstance(get_save_strategy(platform_slug="snes"), DefaultSavePerGameStrategy)


def test_getSaveStrategy_unmappedCoreFallback_defaultsToDefaultSavePerGame():
    # Arrange & Act
    strat = get_save_strategy(core_name="nonexistent_fantasy_core", platform_slug="fantasy_system")

    # Assert
    assert isinstance(strat, DefaultSavePerGameStrategy)


def test_getSaveStrategy_filenameExtensionStripping_normalizesCoreName():
    # Arrange & Act
    strat_dll = get_save_strategy(core_name="pcsx2_libretro.dll")
    strat_so = get_save_strategy(core_name="dolphin_libretro.so")
    strat_dylib = get_save_strategy(core_name="citra_libretro.dylib")

    # Assert
    assert isinstance(strat_dll, SharedMemoryCardStrategy)
    assert isinstance(strat_so, MemoryCardPerGameStrategy)
    assert isinstance(strat_dylib, MemoryCardPerGameStrategy)


def test_getSaveStrategy_allCompatibilityDocSupportedSystems_resolveCorrectly():
    """Verify all 14 systems in docs/compatibility.md with ✅/☑️ resolve to expected save strategies."""
    expected_mappings = [
        # 1. NES / Famicom
        ("nestopia_libretro", "nes", DefaultSavePerGameStrategy),
        # 2. Game Boy
        ("sameboy_libretro", "gb", DefaultSavePerGameStrategy),
        # 3. Super Nintendo
        ("snes9x_libretro", "snes", DefaultSavePerGameStrategy),
        # 4. Nintendo 64
        ("mupen64plus_next_libretro", "n64", DefaultSavePerGameStrategy),
        # 5. Game Boy Color
        ("sameboy_libretro", "gbc", DefaultSavePerGameStrategy),
        # 6. Game Boy Advance
        ("mgba_libretro", "gba", DefaultSavePerGameStrategy),
        # 7. Nintendo GameCube
        ("dolphin_libretro", "gc", MemoryCardPerGameStrategy),
        # 8. Nintendo DS
        ("melonds_libretro", "nds", DefaultSavePerGameStrategy),
        # 9. Nintendo Wii
        ("dolphin_libretro", "wii", MemoryCardPerGameStrategy),
        # 10. Nintendo 3DS
        ("citra_libretro", "3ds", MemoryCardPerGameStrategy),
        # 11. Sega Master System
        ("genesis_plus_gx_libretro", "sms", DefaultSavePerGameStrategy),
        # 12. Sega Dreamcast
        ("flycast_libretro", "dc", SharedMemoryCardStrategy),
        # 13. PlayStation (PS1)
        ("pcsx_rearmed_libretro", "ps1", DefaultSavePerGameStrategy),
        # 14. PlayStation 2
        ("pcsx2_libretro", "ps2", SharedMemoryCardStrategy),
    ]

    for core_name, platform_slug, expected_cls in expected_mappings:
        strat_by_core = get_save_strategy(core_name=core_name)
        strat_by_platform = get_save_strategy(platform_slug=platform_slug)
        strat_by_both = get_save_strategy(core_name=core_name, platform_slug=platform_slug)

        assert isinstance(
            strat_by_core, expected_cls
        ), f"Failed resolving core {core_name}: got {type(strat_by_core).__name__}, expected {expected_cls.__name__}"
        assert isinstance(
            strat_by_platform, expected_cls
        ), f"Failed resolving platform {platform_slug}: got {type(strat_by_platform).__name__}, expected {expected_cls.__name__}"
        assert isinstance(
            strat_by_both, expected_cls
        ), f"Failed resolving core {core_name} + platform {platform_slug}: got {type(strat_by_both).__name__}, expected {expected_cls.__name__}"
