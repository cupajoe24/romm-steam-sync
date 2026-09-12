"""High-level save synchronization interface layer delegating to save strategies."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.service_layer.save_strategies import (
    CORE_SAVE_STRATEGY_MAP,
    RETROARCH_SAVE_EXTENSIONS,
    SAVE_STRATEGY_REGISTRY,
    BaseSaveStrategy,
    DefaultSavePerGameStrategy,
    MemoryCardPerGameStrategy,
    SharedMemoryCardStrategy,
    calculate_save_hash,
    compute_sync_action,
    get_save_strategy,
    parse_iso_to_epoch,
    quarantine_local_save,
)

logger = logging.getLogger(__name__)


def find_local_save_file(
    rom_path: str,
    platform_slug: str = "",
    configured_retroarch_path: str = "",
    remote_ext: str = "",
    core_name: str = "",
    strategy_name: str = "",
    **kwargs: Any,
) -> Tuple[Optional[Path], Path]:
    """Locate existing local save file or candidate destination using appropriate strategy.

    Args:
        rom_path: Path to ROM file.
        platform_slug: Platform identifier slug.
        configured_retroarch_path: Configured RetroArch binary path.
        remote_ext: Extension of remote save file.
        core_name: Libretro core identifier string.
        strategy_name: Optional explicit save strategy override.
        **kwargs: Additional parameters forwarded to strategy.

    Returns:
        Tuple of (existing_local_save_path_or_none, default_target_path).
    """
    strategy = get_save_strategy(
        core_name=core_name,
        platform_slug=platform_slug,
        strategy_name=strategy_name,
    )
    return strategy.find_local_save_file(
        rom_path=rom_path,
        platform_slug=platform_slug,
        configured_retroarch_path=configured_retroarch_path,
        remote_ext=remote_ext,
        core_name=core_name,
        **kwargs,
    )


class SaveSyncEngine:
    """Engine orchestrating pre-launch and post-launch save synchronization."""

    @staticmethod
    def compute_sync_action(
        local_exists: bool,
        local_hash: Optional[str],
        local_mtime: Optional[float],
        remote_save: Optional[Dict[str, Any]],
        local_size: Optional[int] = None,
        last_sync_hash: Optional[str] = None,
        last_sync_server_hash: Optional[str] = None,
        last_sync_local_size: Optional[int] = None,
    ) -> str:
        """Evaluate sync action for a save file according to Gavel matrix.

        Args:
            local_exists: Whether local save exists.
            local_hash: Hash of local save file.
            local_mtime: Local file mtime timestamp.
            remote_save: Remote save metadata dictionary from RomM.
            local_size: Local file size in bytes.
            last_sync_hash: Baseline hash from previous sync.
            last_sync_server_hash: Baseline server hash from previous sync.
            last_sync_local_size: Baseline local size from previous sync.

        Returns:
            One of: 'DOWNLOAD', 'UPLOAD', 'NO_OP', 'CONFLICT'.
        """
        return compute_sync_action(
            local_exists,
            local_hash,
            local_mtime,
            remote_save,
            local_size=local_size,
            last_sync_hash=last_sync_hash,
            last_sync_server_hash=last_sync_server_hash,
            last_sync_local_size=last_sync_local_size,
        )

    @classmethod
    def sync_pre_launch(
        cls,
        rom_id: int,
        rom_path: str,
        platform_slug: str,
        client: RomMApiClient,
        configured_retroarch_path: str = "",
        slot: str = "autosave",
        core_name: str = "",
        strategy_name: str = "",
    ) -> Tuple[str, str, Optional[Dict[str, Any]], Path]:
        """Perform pre-launch save sync check and automatic download/upload if unambiguous.

        Args:
            rom_id: RomM identifier of the game.
            rom_path: Path to the ROM file.
            platform_slug: Platform identifier slug.
            client: RomMApiClient instance.
            configured_retroarch_path: Configured RetroArch path.
            slot: Target save slot.
            core_name: Libretro core identifier.
            strategy_name: Optional explicit save strategy name override.

        Returns:
            Tuple of (action_decision, reason_message, remote_save_dict, local_save_path).
        """
        strategy = get_save_strategy(
            core_name=core_name,
            platform_slug=platform_slug,
            strategy_name=strategy_name,
        )
        return strategy.sync_pre_launch(
            rom_id=rom_id,
            rom_path=rom_path,
            platform_slug=platform_slug,
            client=client,
            configured_retroarch_path=configured_retroarch_path,
            slot=slot,
            core_name=core_name,
        )

    @classmethod
    def sync_post_launch(
        cls,
        rom_id: int,
        save_path: str,
        client: RomMApiClient,
        slot: str = "autosave",
        platform_slug: str = "",
        configured_retroarch_path: str = "",
        core_name: str = "",
        strategy_name: str = "",
        rom_path: str = "",
    ) -> Tuple[bool, str]:
        """Perform post-launch save upload after RetroArch process exits.

        Args:
            rom_id: RomM identifier of the game.
            save_path: Path to the save file.
            client: RomMApiClient instance.
            slot: Target save slot.
            platform_slug: Platform identifier slug.
            configured_retroarch_path: Configured RetroArch path.
            core_name: Libretro core identifier.
            strategy_name: Optional explicit save strategy name override.
            rom_path: Path to the ROM.

        Returns:
            Tuple of (success_boolean, status_message).
        """
        strategy = get_save_strategy(
            core_name=core_name,
            platform_slug=platform_slug,
            strategy_name=strategy_name,
        )
        return strategy.sync_post_launch(
            rom_id=rom_id,
            save_path=save_path,
            client=client,
            slot=slot,
            platform_slug=platform_slug,
            configured_retroarch_path=configured_retroarch_path,
            rom_path=rom_path,
            core_name=core_name,
        )


__all__ = [
    "BaseSaveStrategy",
    "CORE_SAVE_STRATEGY_MAP",
    "DefaultSavePerGameStrategy",
    "MemoryCardPerGameStrategy",
    "RETROARCH_SAVE_EXTENSIONS",
    "SAVE_STRATEGY_REGISTRY",
    "SaveSyncEngine",
    "SharedMemoryCardStrategy",
    "calculate_save_hash",
    "compute_sync_action",
    "find_local_save_file",
    "get_save_strategy",
    "parse_iso_to_epoch",
    "quarantine_local_save",
]
