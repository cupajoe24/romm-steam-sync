"""Memory card per game save strategy for emulators/cores using per-game memory cards."""

import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from romm_steam_sync.adapters.retroarch_launcher import RetroArchLauncher
from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.domain import RomSaveSyncState
from romm_steam_sync.domain.platform import (
    lookup_platform_mapping,
    normalize_platform_slug,
    strip_core_suffix,
)
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.service_layer.gavel import compute_sync_action
from romm_steam_sync.service_layer.save_strategies.base import BaseSaveStrategy
from romm_steam_sync.service_layer.save_strategies.default_save_per_game import (
    calculate_save_hash,
    quarantine_local_save,
)
from romm_steam_sync.service_layer.save_strategies.handlers.base import (
    BaseMemoryCardHandler,
    sanitize_filename,
)
from romm_steam_sync.service_layer.save_strategies.handlers.citra import (
    Citra3DSHandler,
    unpack_3ds_save_archive,
)
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin_gamecube import (
    DolphinGameCubeHandler,
)
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin_wii import (
    DolphinWiiHandler,
    unpack_wii_save_archive,
)
import zipfile

logger = logging.getLogger(__name__)



class GenericMemoryCardHandler(BaseMemoryCardHandler):
    """Generic fallback handler for memory card per game emulators/cores."""

    def extract_rom_metadata(self, rom_path: str) -> Dict[str, Any]:
        """Extract basic ROM metadata from file path.

        Args:
            rom_path: Path to the ROM file.

        Returns:
            Dictionary containing basic game title metadata.
        """
        stem = Path(rom_path).stem if rom_path else ""
        return {
            "game_code": "",
            "maker_code": "",
            "region": "",
            "title": stem,
            "valid_header": False,
        }

    def get_save_directories(
        self,
        configured_retroarch_path: str = "",
        rom_path: str = "",
        platform_slug: str = "",
    ) -> List[Path]:
        """Discover candidate save directories on disk.

        Args:
            configured_retroarch_path: Configured RetroArch path.
            rom_path: Path to ROM.
            platform_slug: Platform identifier slug.

        Returns:
            List of existing candidate save directories.
        """
        candidate_dirs: List[Path] = []
        ra_exe = RetroArchLauncher.resolve_retroarch_binary(
            configured_retroarch_path
        )
        if ra_exe:
            candidate_dirs.append(Path(ra_exe).parent / "saves")

        home = Path.home()
        if sys.platform == "win32":
            candidate_dirs.extend([
                home / "AppData" / "Roaming" / "RetroArch" / "saves",
                Path(r"C:\RetroArch-Win64\saves"),
                Path(r"C:\Program Files\RetroArch-Win64\saves"),
            ])
        elif sys.platform == "darwin":
            candidate_dirs.append(
                home / "Library" / "Application Support" / "RetroArch" / "saves"
            )
        else:
            candidate_dirs.extend([
                home / ".config" / "retroarch" / "saves",
                home
                / ".var"
                / "app"
                / "org.libretro.RetroArch"
                / "config"
                / "retroarch"
                / "saves",
                home
                / "snap"
                / "retroarch"
                / "current"
                / ".config"
                / "retroarch"
                / "saves",
            ])

        if rom_path:
            candidate_dirs.append(Path(rom_path).parent)

        return candidate_dirs

    def resolve_target_save_path(
        self,
        save_dirs: List[Path],
        rom_path: str,
        remote_filename: str = "",
        remote_ext: str = "",
        platform_slug: str = "",
    ) -> Path:
        """Resolve standard target save path when creating a new save.

        Args:
            save_dirs: Candidate save directories.
            rom_path: Path to ROM file.
            remote_filename: Optional filename on RomM server.
            remote_ext: Optional remote save extension.
            platform_slug: Platform slug.

        Returns:
            Resolved destination Path object.
        """
        primary_dir = save_dirs[0] if save_dirs else Path(".")
        if remote_filename:
            return primary_dir / remote_filename
        ext = f".{remote_ext.lstrip('.')}" if remote_ext else ".raw"
        stem = Path(rom_path).stem if rom_path else "game"
        return primary_dir / f"{sanitize_filename(stem)}{ext}"

    def find_existing_save(
        self,
        save_dirs: List[Path],
        rom_path: str,
        remote_filename: str = "",
        remote_ext: str = "",
        platform_slug: str = "",
    ) -> Optional[Path]:
        """Search save directories for existing game memory card file.

        Args:
            save_dirs: List of candidate directories.
            rom_path: Path to ROM.
            remote_filename: Optional remote filename.
            remote_ext: Optional remote extension.
            platform_slug: Platform slug.

        Returns:
            Path to existing save file or None if not found.
        """
        stem = Path(rom_path).stem if rom_path else ""
        exts = [".raw", ".gci", ".sav", ".srm", ".gcp"]
        if remote_ext:
            clean_ext = f".{remote_ext.lstrip('.')}"
            if clean_ext not in exts:
                exts.insert(0, clean_ext)

        for s_dir in save_dirs:
            if not s_dir.exists() or not s_dir.is_dir():
                continue
            if remote_filename:
                cand = s_dir / remote_filename
                if cand.is_file():
                    return cand
            for ext in exts:
                cand = s_dir / f"{stem}{ext}"
                if cand.is_file():
                    return cand
        return None


# Registry of platform and core handlers
_HANDLER_REGISTRY: Dict[str, BaseMemoryCardHandler] = {}
_DEFAULT_DOLPHIN_HANDLER = DolphinGameCubeHandler()
_DEFAULT_WII_HANDLER = DolphinWiiHandler()
_DEFAULT_CITRA_HANDLER = Citra3DSHandler()
_DEFAULT_GENERIC_HANDLER = GenericMemoryCardHandler()

# Default core & platform mappings (GameCube / Dolphin)
for k in [
    "dolphin_libretro",
    "dolphin",
    "dolphin_launcher",
    "gc",
    "ngc",
    "gamecube",
    "game-cube",
    "game cube",
    "nintendo-gamecube",
    "nintendo gamecube",
    "nintendo-game-cube",
    "nintendo game cube",
    "nintendo-gc",
    "nintendo gc",
    "nintendo-ngc",
    "nintendo ngc",
]:
    _HANDLER_REGISTRY[k] = _DEFAULT_DOLPHIN_HANDLER

# Default core & platform mappings (Wii / Dolphin)
for k in [
    "wii",
    "nintendo-wii",
    "nintendo wii",
    "nintendo_wii",
    "wiiu",
    "nintendo-wii-u",
    "nintendo wii u",
    "nintendo_wii_u",
]:
    _HANDLER_REGISTRY[k] = _DEFAULT_WII_HANDLER

# Default core & platform mappings (3DS / Citra)
for k in [
    "citra_libretro",
    "citra",
    "citra2018_libretro",
    "citra2018",
    "3ds",
    "n3ds",
    "nintendo-3ds",
    "nintendo 3ds",
    "nintendo_3ds",
]:
    _HANDLER_REGISTRY[k] = _DEFAULT_CITRA_HANDLER



def register_handler(key: str, handler: BaseMemoryCardHandler) -> None:
    """Register a custom platform/core memory card handler.

    Args:
        key: Core or platform key name.
        handler: BaseMemoryCardHandler instance.
    """
    _HANDLER_REGISTRY[key.lower().strip()] = handler


def get_handler(
    core_name: str = "", platform_slug: str = ""
) -> BaseMemoryCardHandler:
    """Resolve the appropriate BaseMemoryCardHandler for a core or platform.

    Args:
        core_name: Optional core identifier.
        platform_slug: Optional platform slug.

    Returns:
        Matched BaseMemoryCardHandler instance.
    """
    clean_core = strip_core_suffix(core_name.lower().strip()) if core_name else ""

    # If platform specifies Wii, always route to Wii handler even if core is dolphin_libretro
    _, clean_platform, clean_platform_no_hyphen = normalize_platform_slug(platform_slug)
    for plat in [clean_platform, clean_platform_no_hyphen]:
        if plat in ["wii", "nintendowii", "wiiu", "nintendowiiu"]:
            return _DEFAULT_WII_HANDLER

    # Check platform slug in handler registry
    handler = lookup_platform_mapping(_HANDLER_REGISTRY, platform_slug)
    if handler is not None:
        return handler

    if clean_core in _HANDLER_REGISTRY:
        return _HANDLER_REGISTRY[clean_core]

    return _DEFAULT_GENERIC_HANDLER



class MemoryCardPerGameStrategy(BaseSaveStrategy):
    """Save strategy for platforms/cores with individual memory cards per game (e.g. GameCube / Dolphin)."""

    name: str = "memory_card_per_game"

    def find_local_save_file(
        self,
        rom_path: str,
        platform_slug: str = "",
        configured_retroarch_path: str = "",
        remote_ext: str = "",
        remote_filename: str = "",
        core_name: str = "",
        **kwargs: Any,
    ) -> Tuple[Optional[Path], Path]:
        """Locate local memory card save file for the game and determine primary target path.

        Args:
            rom_path: Path to ROM.
            platform_slug: Platform identifier slug.
            configured_retroarch_path: Configured RetroArch executable path.
            remote_ext: Optional remote extension.
            remote_filename: Optional remote filename.
            core_name: Libretro core identifier.
            **kwargs: Extra parameters.

        Returns:
            Tuple of (existing_save_path_or_none, fallback_target_path).
        """
        handler = get_handler(core_name=core_name, platform_slug=platform_slug)
        save_dirs = handler.get_save_directories(
            configured_retroarch_path=configured_retroarch_path,
            rom_path=rom_path,
            platform_slug=platform_slug,
        )
        existing = handler.find_existing_save(
            save_dirs=save_dirs,
            rom_path=rom_path,
            remote_filename=remote_filename,
            remote_ext=remote_ext,
            platform_slug=platform_slug,
        )
        target = handler.resolve_target_save_path(
            save_dirs=save_dirs,
            rom_path=rom_path,
            remote_filename=remote_filename,
            remote_ext=remote_ext,
            platform_slug=platform_slug,
        )
        return existing, target

    def sync_pre_launch(
        self,
        rom_id: int,
        rom_path: str,
        platform_slug: str,
        client: RomMApiClient,
        configured_retroarch_path: str = "",
        slot: str = "autosave",
        core_name: str = "",
        **kwargs: Any,
    ) -> Tuple[str, str, Optional[Dict[str, Any]], Path]:
        """Perform pre-launch save sync check and automatic download/upload if unambiguous.

        Args:
            rom_id: RomM identifier of the game.
            rom_path: Path to ROM.
            platform_slug: Platform slug.
            client: RomMApiClient instance.
            configured_retroarch_path: Configured RetroArch path.
            slot: Target save slot.
            core_name: Libretro core name.
            **kwargs: Extra parameters.

        Returns:
            Tuple of (action_decision, reason_message, remote_save, target_save_path).
        """
        logger.info(
            "Executing pre-launch save sync [memory_card_per_game] for rom_id %s (platform: %s, slot: %s)",
            rom_id,
            platform_slug,
            slot,
        )
        remote_saves = client.get_saves(rom_id, slot=slot)
        remote_save = remote_saves[0] if remote_saves else None

        remote_ext = ""
        remote_filename = ""
        if remote_save:
            remote_filename = (
                remote_save.get("file_name") or remote_save.get("name") or ""
            )
            remote_ext = remote_save.get("file_extension") or Path(
                remote_filename
            ).suffix.lstrip(".")

        existing_local, default_target = self.find_local_save_file(
            rom_path=rom_path,
            platform_slug=platform_slug,
            configured_retroarch_path=configured_retroarch_path,
            remote_ext=remote_ext,
            remote_filename=remote_filename,
            core_name=core_name,
        )

        target_save_path = existing_local if existing_local else default_target
        local_exists = existing_local is not None and existing_local.exists()

        local_hash = (
            calculate_save_hash(str(target_save_path)) if local_exists else None
        )
        local_mtime = target_save_path.stat().st_mtime if local_exists else None
        local_size = target_save_path.stat().st_size if local_exists else None

        (
            last_sync_hash,
            last_sync_server_hash,
            last_sync_local_size,
        ) = self._load_baseline(rom_id, target_save_path.name)

        action = compute_sync_action(
            local_exists=local_exists,
            local_hash=local_hash,
            local_mtime=local_mtime,
            remote_save=remote_save,
            local_size=local_size,
            last_sync_hash=last_sync_hash,
            last_sync_server_hash=last_sync_server_hash,
            last_sync_local_size=last_sync_local_size,
        )
        logger.info(
            "Evaluated pre-launch save sync action: %s for rom_id %s (local_exists: %s, target: %s)",
            action,
            rom_id,
            local_exists,
            target_save_path,
        )

        def _record_baseline() -> None:
            """Record latest save baseline to local SQLite database."""
            BaseSaveStrategy._record_baseline(
                self, rom_id, target_save_path, slot=slot, remote_save=remote_save
            )


        if action == "DOWNLOAD" and remote_save:
            save_id = remote_save.get("id")
            if save_id:
                if local_exists:
                    quarantine_local_save(str(target_save_path))

                # Ensure destination directory exists (e.g. dolphin-emu/User/GC/USA/Card A)
                target_save_path.parent.mkdir(parents=True, exist_ok=True)

                success = client.download_save_content(
                    save_id, str(target_save_path)
                )
                if success:
                    # If downloaded save is a 3DS or Wii zip archive, extract entries into emulated data directory
                    if (
                        target_save_path.is_file()
                        and zipfile.is_zipfile(target_save_path)
                    ):
                        if "nintendo 3ds" in str(target_save_path).lower():
                            dest_data_dir = (
                                target_save_path.parent / "00000001"
                                if target_save_path.name.lower().endswith(".zip")
                                else target_save_path.parent
                            )
                            unpack_3ds_save_archive(target_save_path, dest_data_dir)
                        elif "wii" in str(target_save_path).lower() and "title" in str(target_save_path).lower():
                            dest_data_dir = (
                                target_save_path.parent / "data"
                                if target_save_path.parent.name != "data"
                                else target_save_path.parent
                            )
                            unpack_wii_save_archive(target_save_path, dest_data_dir)

                    logger.info(
                        "Downloaded latest save from RomM to %s",
                        target_save_path,
                    )
                    _record_baseline()
                    return (
                        "DOWNLOAD",
                        "Downloaded latest save from RomM.",
                        remote_save,
                        target_save_path,
                    )

                logger.error(
                    "Failed to download save content (save_id %s) from RomM",
                    save_id,
                )
                return (
                    "ERROR",
                    "Failed to download save file from RomM.",
                    remote_save,
                    target_save_path,
                )

        if action == "UPLOAD" and local_exists:
            try:
                save_id = remote_save.get("id") if remote_save else None
                res = client.upload_save(
                    rom_id, str(target_save_path), save_id=save_id, slot=slot
                )
                if isinstance(res, dict) and res.get("content_hash"):
                    remote_save = res
                _record_baseline()
                return (
                    "UPLOAD",
                    "Uploaded local save to RomM.",
                    remote_save,
                    target_save_path,
                )
            except Exception as e:
                logger.error("Failed to upload save to RomM: %s", e)
                return (
                    "ERROR",
                    f"Failed to upload save: {e}",
                    remote_save,
                    target_save_path,
                )

        if action == "NO_OP":
            _record_baseline()
            return (
                "NO_OP",
                "Save file is up to date.",
                remote_save,
                target_save_path,
            )

        if action == "CONFLICT":
            return (
                "CONFLICT",
                "Save data conflict detected.",
                remote_save,
                target_save_path,
            )

        return action, "Save sync complete.", remote_save, target_save_path

    def sync_post_launch(
        self,
        rom_id: int,
        save_path: str,
        client: RomMApiClient,
        slot: str = "autosave",
        platform_slug: str = "",
        configured_retroarch_path: str = "",
        rom_path: str = "",
        core_name: str = "",
        **kwargs: Any,
    ) -> Tuple[bool, str]:
        """Perform post-launch save upload after emulator process exits.

        Args:
            rom_id: RomM identifier of the game.
            save_path: Path to the save file.
            client: RomMApiClient instance.
            slot: Target save slot.
            platform_slug: Platform slug.
            configured_retroarch_path: Configured RetroArch executable path.
            rom_path: Path to ROM.
            core_name: Libretro core name.
            **kwargs: Extra parameters.

        Returns:
            Tuple of (success_boolean, message).
        """
        target_path: Optional[Path] = None

        if save_path and Path(save_path).is_file():
            save_p = Path(save_path)
            # If save_path points directly to a save file (.gci, .raw, .sav, .srm, main, etc.), use it
            if (
                save_p.name.lower() in ["main", "main.sav", "main.bin"]
                or save_p.suffix.lower() in [
                    ".gci",
                    ".raw",
                    ".sav",
                    ".srm",
                    ".gcp",
                    ".bin",
                    ".dat",
                ]
            ):
                target_path = save_p

        if not target_path:
            # Locate save file using ROM path and handler
            effective_rom_path = rom_path or save_path
            existing, _ = self.find_local_save_file(
                rom_path=effective_rom_path,
                platform_slug=platform_slug,
                configured_retroarch_path=configured_retroarch_path,
                core_name=core_name,
            )
            if existing and existing.exists():
                target_path = existing



        if not target_path or not target_path.exists():
            logger.info(
                "No local memory card save file found for rom_id %s post-launch to upload.",
                rom_id,
            )
            return True, "No local save file found post-launch."

        try:
            save_id, remote_save = self._match_remote_save(
                client, rom_id, target_path, slot=slot
            )
            res = client.upload_save(
                rom_id, str(target_path), save_id=save_id, slot=slot
            )
            if isinstance(res, dict) and res.get("content_hash"):
                remote_save = res

            self._record_baseline(
                rom_id, target_path, slot=slot, remote_save=remote_save
            )
            logger.info(
                "Successfully uploaded save file %s (slot: %s) to RomM post-launch.",
                target_path.name,
                slot,
            )
            return (
                True,
                f"Successfully uploaded save file ({target_path.name}) to RomM.",
            )
        except Exception as e:
            logger.error(
                "Post-launch save upload failed for rom_id %s: %s", rom_id, e
            )
            return False, f"Post-launch save upload failed: {e}"

