"""Core to strategy mappings and strategy registry lookup functionality."""

import logging
from typing import Dict

from romm_steam_sync.adapters.retroarch_launcher import DEFAULT_CORE_MAPPINGS
from romm_steam_sync.domain.platform import (
    lookup_platform_mapping,
    strip_core_suffix,
)
from romm_steam_sync.service_layer.save_strategies.base import BaseSaveStrategy
from romm_steam_sync.service_layer.save_strategies.default_save_per_game import (
    DefaultSavePerGameStrategy,
)
from romm_steam_sync.service_layer.save_strategies.memory_card_per_game import (
    MemoryCardPerGameStrategy,
)
from romm_steam_sync.service_layer.save_strategies.shared_memory_card import (
    SharedMemoryCardStrategy,
)

logger = logging.getLogger(__name__)

# Explicit mapping of RetroArch libretro core names to save strategy names.
CORE_SAVE_STRATEGY_MAP: Dict[str, str] = {
    # NES
    "nestopia_libretro": "default_save_per_game",
    "nestopia": "default_save_per_game",
    "fceumm_libretro": "default_save_per_game",
    "fceumm": "default_save_per_game",
    "mesen_libretro": "default_save_per_game",
    "mesen": "default_save_per_game",
    # SNES
    "snes9x_libretro": "default_save_per_game",
    "snes9x": "default_save_per_game",
    "bsnes_libretro": "default_save_per_game",
    "bsnes": "default_save_per_game",
    "snes9x2010_libretro": "default_save_per_game",
    "snes9x2010": "default_save_per_game",
    # N64
    "mupen64plus_next_libretro": "default_save_per_game",
    "mupen64plus_next": "default_save_per_game",
    "parallel_n64_libretro": "default_save_per_game",
    "parallel_n64": "default_save_per_game",
    # GB & GBC
    "sameboy_libretro": "default_save_per_game",
    "sameboy": "default_save_per_game",
    "gambatte_libretro": "default_save_per_game",
    "gambatte": "default_save_per_game",
    # GBA
    "mgba_libretro": "default_save_per_game",
    "mgba": "default_save_per_game",
    "vba_next_libretro": "default_save_per_game",
    "vba_next": "default_save_per_game",
    "gpsp_libretro": "default_save_per_game",
    "gpsp": "default_save_per_game",
    # Nintendo DS (NDS)
    "melonds_libretro": "default_save_per_game",
    "melonds": "default_save_per_game",
    "desmume_libretro": "default_save_per_game",
    "desmume": "default_save_per_game",
    "nds": "default_save_per_game",
    "ds": "default_save_per_game",
    "nintendo-ds": "default_save_per_game",
    "nintendo ds": "default_save_per_game",
    "nintendo_ds": "default_save_per_game",
    # Sega Master System (SMS) & Genesis
    "genesis_plus_gx_libretro": "default_save_per_game",
    "genesis_plus_gx": "default_save_per_game",
    "gearsystem_libretro": "default_save_per_game",
    "gearsystem": "default_save_per_game",
    "sms": "default_save_per_game",
    "mastersystem": "default_save_per_game",
    "master-system": "default_save_per_game",
    "master system": "default_save_per_game",
    "sega-master-system": "default_save_per_game",
    "sega master system": "default_save_per_game",
    # PlayStation (PS1 / PSX)
    "pcsx_rearmed_libretro": "default_save_per_game",
    "pcsx_rearmed": "default_save_per_game",
    "beetle_psx_hw_libretro": "default_save_per_game",
    "beetle_psx_hw": "default_save_per_game",
    "beetle_psx_libretro": "default_save_per_game",
    "beetle_psx": "default_save_per_game",
    "duckstation_libretro": "default_save_per_game",
    "duckstation": "default_save_per_game",
    "mednafen_psx_libretro": "default_save_per_game",
    "mednafen_psx": "default_save_per_game",
    "ps": "default_save_per_game",
    "ps1": "default_save_per_game",
    "psx": "default_save_per_game",
    "playstation": "default_save_per_game",
    "playstation-1": "default_save_per_game",
    "playstation 1": "default_save_per_game",
    "sony-playstation": "default_save_per_game",
    "sony playstation": "default_save_per_game",
    # PS2 / PCSX2 / LRPS2
    "pcsx2_libretro": "shared_memory_card",
    "pcsx2": "shared_memory_card",
    "lrps2_libretro": "shared_memory_card",
    "lrps2": "shared_memory_card",
    "playstation2": "shared_memory_card",
    "playstation-2": "shared_memory_card",
    "playstation_2": "shared_memory_card",
    "playstation 2": "shared_memory_card",
    "sony-playstation-2": "shared_memory_card",
    "sony_playstation_2": "shared_memory_card",
    "sony playstation 2": "shared_memory_card",
    "ps2": "shared_memory_card",
    "ps-2": "shared_memory_card",
    "ps_2": "shared_memory_card",
    "sony-ps2": "shared_memory_card",
    "sony_ps2": "shared_memory_card",
    "sony ps2": "shared_memory_card",
    # Dreamcast / Flycast / Naomi / Atomiswave
    "flycast_libretro": "shared_memory_card",
    "flycast": "shared_memory_card",
    "flycast_gles2_libretro": "shared_memory_card",
    "flycast_gles2": "shared_memory_card",
    "reicast_libretro": "shared_memory_card",
    "reicast": "shared_memory_card",
    "dc": "shared_memory_card",
    "dreamcast": "shared_memory_card",
    "sega-dreamcast": "shared_memory_card",
    "sega_dreamcast": "shared_memory_card",
    "naomi": "shared_memory_card",
    "naomi2": "shared_memory_card",
    "naomigd": "shared_memory_card",
    "atomiswave": "shared_memory_card",
    # GameCube / Dolphin
    "dolphin_libretro": "memory_card_per_game",
    "dolphin": "memory_card_per_game",
    "dolphin_launcher": "memory_card_per_game",
    "gamecube": "memory_card_per_game",
    "game-cube": "memory_card_per_game",
    "game cube": "memory_card_per_game",
    "gc": "memory_card_per_game",
    "ngc": "memory_card_per_game",
    "nintendo-gamecube": "memory_card_per_game",
    "nintendo gamecube": "memory_card_per_game",
    "nintendo-game-cube": "memory_card_per_game",
    "nintendo game cube": "memory_card_per_game",
    "nintendo-gc": "memory_card_per_game",
    "nintendo gc": "memory_card_per_game",
    "nintendo-ngc": "memory_card_per_game",
    "nintendo ngc": "memory_card_per_game",
    # Nintendo Wii
    "wii": "memory_card_per_game",
    "nintendo-wii": "memory_card_per_game",
    "nintendo wii": "memory_card_per_game",
    "nintendo_wii": "memory_card_per_game",
    "wiiu": "memory_card_per_game",
    "nintendo-wii-u": "memory_card_per_game",
    "nintendo wii u": "memory_card_per_game",
    "nintendo_wii_u": "memory_card_per_game",
    # Nintendo 3DS / Citra
    "citra_libretro": "memory_card_per_game",
    "citra": "memory_card_per_game",
    "citra2018_libretro": "memory_card_per_game",
    "citra2018": "memory_card_per_game",
    "3ds": "memory_card_per_game",
    "n3ds": "memory_card_per_game",
    "nintendo-3ds": "memory_card_per_game",
    "nintendo 3ds": "memory_card_per_game",
    "nintendo_3ds": "memory_card_per_game",
}



SAVE_STRATEGY_REGISTRY: Dict[str, BaseSaveStrategy] = {
    "default_save_per_game": DefaultSavePerGameStrategy(),
    "shared_memory_card": SharedMemoryCardStrategy(),
    "memory_card_per_game": MemoryCardPerGameStrategy(),
}


def get_save_strategy(
    core_name: str = "",
    platform_slug: str = "",
    strategy_name: str = "",
) -> BaseSaveStrategy:
    """Resolve SaveStrategy instance by explicit strategy_name, core_name, or platform_slug.

    Defaults to 'default_save_per_game' strategy if no explicit mapping exists.

    Args:
        core_name: Libretro core identifier string.
        platform_slug: Platform identifier slug.
        strategy_name: Optional explicit strategy name override.

    Returns:
        Matched BaseSaveStrategy instance.
    """
    if strategy_name and strategy_name.lower() in SAVE_STRATEGY_REGISTRY:
        return SAVE_STRATEGY_REGISTRY[strategy_name.lower()]

    target_core = strip_core_suffix(core_name.lower().strip()) if core_name else ""

    if not target_core and platform_slug:
        target_core = lookup_platform_mapping(DEFAULT_CORE_MAPPINGS, platform_slug) or ""

    strat_key = (
        CORE_SAVE_STRATEGY_MAP.get(target_core)
        or (lookup_platform_mapping(CORE_SAVE_STRATEGY_MAP, platform_slug) if platform_slug else None)
        or "default_save_per_game"
    )
    logger.debug(
        "Resolved save strategy '%s' for core '%s' (platform: '%s')",
        strat_key,
        core_name or target_core,
        platform_slug,
    )

    return SAVE_STRATEGY_REGISTRY.get(
        strat_key, SAVE_STRATEGY_REGISTRY["default_save_per_game"]
    )
