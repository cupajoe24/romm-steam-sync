"""Platform and core handlers for memory card per game save strategies."""

from romm_steam_sync.service_layer.save_strategies.handlers.base import (
    BaseMemoryCardHandler,
    sanitize_filename,
)
from romm_steam_sync.service_layer.save_strategies.handlers.citra import (
    Citra3DSHandler,
    read_3ds_rom_header,
)
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin import (
    BaseDolphinHandler,
    DolphinHandler,
)
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin_gamecube import (
    DolphinGameCubeHandler,
    read_gc_container_header,
    read_gci_header,
)
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin_wii import (
    DolphinWiiHandler,
    read_wii_disc_header,
    unpack_wii_save_archive,
)

__all__ = [
    "BaseDolphinHandler",
    "BaseMemoryCardHandler",
    "Citra3DSHandler",
    "DolphinGameCubeHandler",
    "DolphinHandler",
    "DolphinWiiHandler",
    "read_3ds_rom_header",
    "read_gc_container_header",
    "read_gci_header",
    "read_wii_disc_header",
    "sanitize_filename",
    "unpack_wii_save_archive",
]

