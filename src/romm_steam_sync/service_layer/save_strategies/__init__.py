"""Platform and emulator core save synchronization strategies."""

from romm_steam_sync.service_layer.save_strategies.base import BaseSaveStrategy
from romm_steam_sync.service_layer.save_strategies.default_save_per_game import (
    RETROARCH_SAVE_EXTENSIONS,
    DefaultSavePerGameStrategy,
    calculate_save_hash,
    compute_sync_action,
    find_local_save_file,
    parse_iso_to_epoch,
    quarantine_local_save,
)
from romm_steam_sync.service_layer.save_strategies.handlers import (
    BaseMemoryCardHandler,
    DolphinGameCubeHandler,
    read_gci_header,
    sanitize_filename,
)
from romm_steam_sync.service_layer.save_strategies.memory_card_per_game import (
    GenericMemoryCardHandler,
    MemoryCardPerGameStrategy,
    get_handler,
    register_handler,
)
from romm_steam_sync.service_layer.save_strategies.registry import (
    CORE_SAVE_STRATEGY_MAP,
    SAVE_STRATEGY_REGISTRY,
    get_save_strategy,
)
from romm_steam_sync.service_layer.save_strategies.shared_memory_card import (
    SharedMemoryCardStrategy,
)

__all__ = [
    "BaseMemoryCardHandler",
    "BaseSaveStrategy",
    "CORE_SAVE_STRATEGY_MAP",
    "DefaultSavePerGameStrategy",
    "DolphinGameCubeHandler",
    "GenericMemoryCardHandler",
    "MemoryCardPerGameStrategy",
    "RETROARCH_SAVE_EXTENSIONS",
    "SAVE_STRATEGY_REGISTRY",
    "SharedMemoryCardStrategy",
    "calculate_save_hash",
    "compute_sync_action",
    "find_local_save_file",
    "get_handler",
    "get_save_strategy",
    "parse_iso_to_epoch",
    "quarantine_local_save",
    "read_gci_header",
    "register_handler",
    "sanitize_filename",
]
