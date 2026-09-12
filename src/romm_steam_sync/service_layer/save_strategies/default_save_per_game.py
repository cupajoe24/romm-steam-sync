"""Default save per game strategy for cartridge and standard core save files (.srm, .sav, .eep, etc.)."""

from datetime import datetime, timezone
import hashlib
import logging
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple
import zipfile

from romm_steam_sync.adapters.retroarch_config import RetroArchConfigAdapter
from romm_steam_sync.adapters.retroarch_launcher import RetroArchLauncher
from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.domain import RomSaveSyncState
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.service_layer.gavel import (
    compute_sync_action as gavel_compute_sync_action,
    parse_iso_to_epoch,
)
from romm_steam_sync.service_layer.save_strategies.base import (
    BaseSaveStrategy,
    calculate_save_hash,
)

logger = logging.getLogger(__name__)

RETROARCH_SAVE_EXTENSIONS: List[str] = [
    ".srm",
    ".sav",
    ".rtc",
    ".eep",  # N64 EEPROM / PokeMini
    ".fla",  # N64 Flash RAM
    ".sra",  # N64 SRAM
    ".mpk",  # N64 MemPak / Controller Pak
    ".dsv",  # Nintendo DS (DeSmuME / melonDS)
    ".bkr",  # Sega Saturn internal backup
    ".bcr",  # Sega Saturn expansion card
    ".smpc",  # Sega Saturn SMPC
    ".brm",  # Sega CD / Mega CD internal backup
    ".mcd",  # PlayStation (PCSX ReARMed / DuckStation memory card)
    ".gme",  # PlayStation DexDrive memory card
    ".flash",  # Neo Geo Pocket / Arcade flash
    ".ngf",  # Neo Geo Pocket RACE save
    ".nvr",  # Amiga / CD32 non-volatile RAM
]


def find_local_save_file(

    rom_path: str,
    platform_slug: str = "",
    configured_retroarch_path: str = "",
    remote_ext: str = "",
    core_name: str = "",
    **kwargs: Any,
) -> Tuple[Optional[Path], Path]:
    """Search candidate directories (and subdirectories) for existing RetroArch save file.

    Resolves the live RetroArch save directory based on retroarch.cfg settings
    (savefiles_in_content_dir, sort_savefiles_by_content_enable, sort_savefiles_enable)
    and searches the resolved directory first. Also inspects legacy and candidate
    directories, automatically migrating any orphaned legacy save files into RetroArch's
    target directory when appropriate.

    Args:
        rom_path: Path to the ROM file.
        platform_slug: Platform slug identifier.
        configured_retroarch_path: Configured path to RetroArch.
        remote_ext: Optional remote save extension.
        core_name: Optional libretro core identifier.
        **kwargs: Unused extra arguments.

    Returns:
        Tuple of (existing_save_path_if_found, default_save_target_path).
    """
    rom_p = Path(rom_path)
    rom_stem = rom_p.stem

    stems_to_try: List[str] = [rom_stem]
    if "_" in rom_stem:
        prefix, rest = rom_stem.split("_", 1)
        if prefix.isdigit() and rest:
            stems_to_try.append(rest)

    # 1. Resolve RetroArch runtime save directory using config adapter
    cfg_adapter = RetroArchConfigAdapter(
        configured_retroarch_path=configured_retroarch_path
    )
    target_dir = cfg_adapter.resolve_save_directory(
        rom_path, platform_slug=platform_slug, core_name=core_name
    )

    fallback_ext = f".{remote_ext.lstrip('.')}" if remote_ext else ".srm"
    default_target = target_dir / f"{rom_stem}{fallback_ext}"

    # Extensions list to search (prioritize remote_ext if provided)
    search_exts = list(RETROARCH_SAVE_EXTENSIONS)
    if remote_ext:
        clean_remote_ext = f".{remote_ext.lstrip('.')}"
        if clean_remote_ext not in search_exts:
            search_exts.insert(0, clean_remote_ext)
        else:
            search_exts.remove(clean_remote_ext)
            search_exts.insert(0, clean_remote_ext)

    # 2. Search primary target directory FIRST
    if target_dir.is_dir():
        for stem in stems_to_try:
            for ext in search_exts:
                cand = target_dir / f"{stem}{ext}"
                if cand.is_file():
                    return cand, cand

    # 3. Secondary candidate directories for legacy saves or unconfigured installations
    candidate_dirs: List[Path] = []
    if target_dir != rom_p.parent:
        candidate_dirs.append(rom_p.parent)

    ra_exe = RetroArchLauncher.resolve_retroarch_binary(
        configured_retroarch_path
    )
    if ra_exe:
        exe_parent = Path(ra_exe).parent
        candidate_dirs.append(exe_parent / "saves")
        if platform_slug:
            candidate_dirs.append(exe_parent / "saves" / platform_slug.lower())

    home = Path.home()
    if sys.platform == "win32":
        candidate_dirs.extend([
            home / "AppData" / "Roaming" / "RetroArch" / "saves",
            Path(r"C:\RetroArch-Win64\saves"),
            Path(r"C:\Program Files\RetroArch-Win64\saves"),
            Path(r"C:\Program Files (x86)\RetroArch-Win64\saves"),
        ])
        if platform_slug:
            candidate_dirs.append(
                home
                / "AppData"
                / "Roaming"
                / "RetroArch"
                / "saves"
                / platform_slug.lower()
            )
    elif sys.platform == "darwin":
        mac_saves = home / "Library" / "Application Support" / "RetroArch" / "saves"
        candidate_dirs.append(mac_saves)
        if platform_slug:
            candidate_dirs.append(mac_saves / platform_slug.lower())
    else:
        linux_saves = home / ".config" / "retroarch" / "saves"
        flatpak_saves = (
            home
            / ".var"
            / "app"
            / "org.libretro.RetroArch"
            / "config"
            / "retroarch"
            / "saves"
        )
        snap_saves = (
            home
            / "snap"
            / "retroarch"
            / "current"
            / ".config"
            / "retroarch"
            / "saves"
        )
        candidate_dirs.extend([linux_saves, flatpak_saves, snap_saves])
        if platform_slug:
            candidate_dirs.append(linux_saves / platform_slug.lower())
            candidate_dirs.append(flatpak_saves / platform_slug.lower())
            candidate_dirs.append(snap_saves / platform_slug.lower())

    # Direct file search in secondary candidate directories
    for c_dir in candidate_dirs:
        if not c_dir.exists() or c_dir == target_dir:
            continue
        for stem in stems_to_try:
            for ext in search_exts:
                cand = c_dir / f"{stem}{ext}"
                if cand.is_file():
                    return cand, default_target

    # Recursive search in secondary candidate directories
    for c_dir in candidate_dirs:
        if not c_dir.exists() or not c_dir.is_dir() or c_dir == target_dir:
            continue
        for stem in stems_to_try:
            for ext in search_exts:
                try:
                    found_matches = list(c_dir.rglob(f"{stem}{ext}"))
                    for match in found_matches:
                        if match.is_file():
                            return match, default_target
                except Exception as e:
                    logger.debug(
                        "rglob error searching for save in %s: %s", c_dir, e
                    )

    return None, default_target


def quarantine_local_save(save_path: str) -> Optional[str]:
    """Back up existing local save file into .romm-backup before overwriting.

    Args:
        save_path: Path to the local save file to quarantine.

    Returns:
        New destination path string if quarantined, or None on error.
    """
    save_p = Path(save_path)
    if not save_p.is_file():
        return None

    backup_dir = save_p.parent / ".romm-backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{save_p.stem}_{timestamp}{save_p.suffix}"
    backup_target = backup_dir / backup_filename

    counter = 1
    while backup_target.exists():
        backup_filename = f"{save_p.stem}_{timestamp}_{counter}{save_p.suffix}"
        backup_target = backup_dir / backup_filename
        counter += 1

    try:
        save_p.rename(backup_target)
        logger.info("Quarantined local save file to %s", backup_target)
        return str(backup_target)
    except Exception as e:
        logger.warning("Failed to quarantine save file %s: %s", save_path, e)
        return None


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
        local_exists: Whether local save file exists.
        local_hash: Computed hash of local save file.
        local_mtime: Local save file modification timestamp.
        remote_save: Remote save metadata dictionary from RomM.
        local_size: Local file size in bytes.
        last_sync_hash: Baseline hash from previous sync.
        last_sync_server_hash: Baseline remote server hash from previous sync.
        last_sync_local_size: Baseline local size from previous sync.

    Returns:
        One of: 'DOWNLOAD', 'UPLOAD', 'NO_OP', 'CONFLICT'.
    """
    return gavel_compute_sync_action(
        local_exists=local_exists,
        local_hash=local_hash,
        local_mtime=local_mtime,
        local_size=local_size,
        remote_save=remote_save,
        last_sync_hash=last_sync_hash,
        last_sync_server_hash=last_sync_server_hash,
        last_sync_local_size=last_sync_local_size,
    )


class DefaultSavePerGameStrategy(BaseSaveStrategy):
    """Default save file strategy handling per-game save files (battery RAM, SRM, SAV, EEPROM)."""

    name: str = "default_save_per_game"

    def find_local_save_file(
        self,
        rom_path: str,
        platform_slug: str = "",
        configured_retroarch_path: str = "",
        remote_ext: str = "",
        core_name: str = "",
        **kwargs: Any,
    ) -> Tuple[Optional[Path], Path]:
        """Locate existing or target save file for a game.

        Args:
            rom_path: Path to the ROM file.
            platform_slug: Platform identifier slug.
            configured_retroarch_path: Configured RetroArch path.
            remote_ext: Extension of remote save.
            core_name: Optional core identifier.
            **kwargs: Extra parameters.

        Returns:
            Tuple of (existing_save_path_or_none, fallback_target_path).
        """
        return find_local_save_file(
            rom_path,
            platform_slug=platform_slug,
            configured_retroarch_path=configured_retroarch_path,
            remote_ext=remote_ext,
            core_name=core_name,
            **kwargs,
        )

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
        """Perform pre-launch save sync evaluation and action.

        Args:
            rom_id: RomM identifier of the game.
            rom_path: Path to local ROM file.
            platform_slug: Platform identifier slug.
            client: RomMApiClient instance.
            configured_retroarch_path: Configured RetroArch executable path.
            slot: Target save slot.
            core_name: Libretro core name.
            **kwargs: Extra arguments.

        Returns:
            Tuple of (action, message, remote_save, target_save_path).
        """
        logger.info(
            "Executing pre-launch save sync [default_save_per_game] for rom_id %s (platform: %s, slot: %s)",
            rom_id,
            platform_slug,
            slot,
        )
        remote_save = self._fetch_remote_save(client, rom_id, slot=slot)

        remote_ext = ""
        if remote_save:
            remote_ext = remote_save.get("file_extension") or Path(
                remote_save.get("name") or remote_save.get("file_name") or ""
            ).suffix.lstrip(".")

        existing_save, target_save_path = self.find_local_save_file(
            rom_path,
            platform_slug=platform_slug,
            configured_retroarch_path=configured_retroarch_path,
            remote_ext=remote_ext,
            core_name=core_name,
            **kwargs,
        )

        local_exists = existing_save is not None and existing_save.exists()
        local_hash = (
            calculate_save_hash(str(existing_save)) if local_exists else None
        )
        local_mtime = existing_save.stat().st_mtime if local_exists else None
        local_size = existing_save.stat().st_size if local_exists else None

        (
            last_sync_hash,
            last_sync_server_hash,
            last_sync_local_size,
        ) = self._load_baseline(rom_id, target_save_path.name)

        action = compute_sync_action(
            local_exists,
            local_hash,
            local_mtime,
            remote_save,
            local_size=local_size,
            last_sync_hash=last_sync_hash,
            last_sync_server_hash=last_sync_server_hash,
            last_sync_local_size=last_sync_local_size,
        )
        logger.info(
            "Evaluated pre-launch save sync action: %s for rom_id %s (local_exists: %s)",
            action,
            rom_id,
            local_exists,
        )

        def _record_baseline() -> None:
            """Record latest save baseline to local SQLite database."""
            BaseSaveStrategy._record_baseline(
                self, rom_id, target_save_path, slot=slot, remote_save=remote_save
            )


        if action == "DOWNLOAD" and remote_save:
            save_id = remote_save.get("id")
            if save_id:
                if local_exists and existing_save:
                    quarantine_local_save(str(existing_save))

                target_save_path.parent.mkdir(parents=True, exist_ok=True)
                success = client.download_save_content(
                    save_id, str(target_save_path)
                )
                if success:
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

        if action == "UPLOAD" and local_exists and existing_save:
            try:
                save_id = remote_save.get("id") if remote_save else None
                res = client.upload_save(
                    rom_id, str(existing_save), save_id=save_id, slot=slot
                )
                if isinstance(res, dict) and res.get("content_hash"):
                    remote_save = res
                _record_baseline()
                if (
                    existing_save != target_save_path
                    and existing_save.exists()
                    and not target_save_path.exists()
                ):
                    try:
                        target_save_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(existing_save, target_save_path)
                        logger.info(
                            "Copied save file %s to runtime RetroArch target %s",
                            existing_save,
                            target_save_path,
                        )
                    except Exception as e:
                        logger.warning(
                            "Failed copying save to target_save_path %s: %s",
                            target_save_path,
                            e,
                        )
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
            if (
                existing_save
                and existing_save != target_save_path
                and existing_save.exists()
                and not target_save_path.exists()
            ):
                try:
                    target_save_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(existing_save, target_save_path)
                    logger.info(
                        "Copied save file %s to runtime RetroArch target %s",
                        existing_save,
                        target_save_path,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed copying save to target_save_path %s: %s",
                        target_save_path,
                        e,
                    )
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
            save_path: Path to the local save file.
            client: RomMApiClient instance.
            slot: Target save slot.
            platform_slug: Platform identifier slug.
            configured_retroarch_path: Configured RetroArch path.
            rom_path: Path to ROM.
            core_name: Libretro core name.
            **kwargs: Extra parameters.

        Returns:
            Tuple of (success_boolean, message).
        """
        save_p = Path(save_path)
        if not save_p.exists():
            logger.info(
                "No local save file found at %s post-launch to upload.",
                save_path,
            )
            return True, "No local save file found post-launch."

        try:
            save_id, remote_save = self._match_remote_save(
                client, rom_id, save_p, slot=slot
            )
            res = client.upload_save(
                rom_id, str(save_p), save_id=save_id, slot=slot
            )
            if isinstance(res, dict) and res.get("content_hash"):
                remote_save = res

            self._record_baseline(
                rom_id, save_p, slot=slot, remote_save=remote_save
            )
            logger.info(
                "Successfully uploaded save file %s (slot: %s) to RomM post-launch.",
                save_p.name,
                slot,
            )
            return (
                True,
                f"Successfully uploaded save file ({save_p.name}) to RomM.",
            )
        except Exception as e:
            logger.error(
                "Post-launch save upload failed for rom_id %s: %s", rom_id, e
            )
            return False, f"Post-launch save upload failed: {e}"

