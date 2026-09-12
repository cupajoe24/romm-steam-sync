"""Shared memory card save strategy for emulators/cores using shared memory card files."""

import logging
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from romm_steam_sync.adapters.retroarch_launcher import (
    DEFAULT_CORE_MAPPINGS,
    RetroArchLauncher,
)
from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.config import get_default_config_dir
from romm_steam_sync.domain.platform import (
    lookup_platform_mapping,
    normalize_platform_slug,
    strip_core_suffix,
)
from romm_steam_sync.domain.save_sync_state import RomSaveSyncState
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.service_layer.save_strategies.base import BaseSaveStrategy
from romm_steam_sync.service_layer.save_strategies.default_save_per_game import (
    calculate_save_hash,
    compute_sync_action,
    quarantine_local_save,
)

logger = logging.getLogger(__name__)

# Map core names / platform slugs to RetroArch system memory card folder names.
SYSTEM_MEMCARD_SUBDIRS: Dict[str, str] = {
    # PS2
    "pcsx2_libretro": "pcsx2",
    "pcsx2": "pcsx2",
    "lrps2_libretro": "pcsx2",
    "lrps2": "pcsx2",
    "playstation2": "pcsx2",
    "playstation-2": "pcsx2",
    "playstation_2": "pcsx2",
    "playstation 2": "pcsx2",
    "sony-playstation-2": "pcsx2",
    "sony_playstation_2": "pcsx2",
    "sony playstation 2": "pcsx2",
    "ps2": "pcsx2",
    "ps-2": "pcsx2",
    "ps_2": "pcsx2",
    "sony-ps2": "pcsx2",
    "sony_ps2": "pcsx2",
    "sony ps2": "pcsx2",
    # Dreamcast / Flycast / Naomi / Atomiswave
    "flycast_libretro": "dc",
    "flycast": "dc",
    "flycast_gles2_libretro": "dc",
    "flycast_gles2": "dc",
    "reicast_libretro": "dc",
    "reicast": "dc",
    "dc": "dc",
    "dreamcast": "dc",
    "sega-dreamcast": "dc",
    "sega_dreamcast": "dc",
    "sega dreamcast": "dc",
    "naomi": "dc",
    "naomi2": "dc",
    "naomigd": "dc",
    "atomiswave": "dc",
}

DEFAULT_MEMCARD_FILENAMES: Dict[str, str] = {
    "pcsx2": "Mcd001.ps2",
    "ps2": "Mcd001.ps2",
    "playstation-2": "Mcd001.ps2",
    "playstation2": "Mcd001.ps2",
    "sony-playstation-2": "Mcd001.ps2",
    "dc": "vmu_save_A1.bin",
    "dreamcast": "vmu_save_A1.bin",
    "sega-dreamcast": "vmu_save_A1.bin",
    "flycast": "vmu_save_A1.bin",
}

SYSTEM_MEMCARD_REL_PATHS: Dict[str, str] = {
    "pcsx2": "pcsx2/memcards",
    "playstation-2": "pcsx2/memcards",
    "playstation2": "pcsx2/memcards",
    "ps2": "pcsx2/memcards",
    "sony-playstation-2": "pcsx2/memcards",
    "dc": "dc",
    "dreamcast": "dc",
    "sega-dreamcast": "dc",
    "flycast": "dc",
}

SYSTEM_MEMCARD_EXTENSIONS: Dict[str, List[str]] = {
    "pcsx2": [".ps2", ".mcd", ".sav", ".raw"],
    "playstation-2": [".ps2", ".mcd", ".sav", ".raw"],
    "playstation2": [".ps2", ".mcd", ".sav", ".raw"],
    "ps2": [".ps2", ".mcd", ".sav", ".raw"],
    "sony-playstation-2": [".ps2", ".mcd", ".sav", ".raw"],
    "dc": [".bin", ".vmu"],
    "dreamcast": [".bin", ".vmu"],
}


def get_memcard_system_folder(
    core_name: str = "", platform_slug: str = ""
) -> str:
    """Resolve RetroArch system memory card subfolder name for a core or platform.

    Args:
        core_name: Libretro core identifier string.
        platform_slug: Platform identifier slug.

    Returns:
        Folder name within RetroArch system directory (e.g. 'pcsx2' or 'dc').
    """
    clean_core = strip_core_suffix(core_name.lower().strip()) if core_name else ""
    if clean_core in SYSTEM_MEMCARD_SUBDIRS:
        return SYSTEM_MEMCARD_SUBDIRS[clean_core]

    if platform_slug:
        matched = lookup_platform_mapping(SYSTEM_MEMCARD_SUBDIRS, platform_slug)
        if matched:
            return matched
        mapped_core = lookup_platform_mapping(DEFAULT_CORE_MAPPINGS, platform_slug)
        if mapped_core and mapped_core in SYSTEM_MEMCARD_SUBDIRS:
            return SYSTEM_MEMCARD_SUBDIRS[mapped_core]

    _, clean_platform, _ = normalize_platform_slug(platform_slug)
    return clean_core or clean_platform or "shared"



def consolidate_local_memcards(
    target_dir: Path,
    canonical_card_name: str = "Mcd001.ps2",
    valid_extensions: Optional[List[str]] = None,
) -> Path:
    """Ensure local game memcard directory contains a consolidated canonical memory card file.

    Args:
        target_dir: Local directory containing game memory card files.
        canonical_card_name: Standardized filename (e.g. 'Mcd001.ps2').
        valid_extensions: Optional list of recognized memory card extensions.

    Returns:
        Path pointing to canonical memory card file.
    """
    canonical_file = target_dir / canonical_card_name
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)
        return canonical_file

    if valid_extensions is None:
        valid_extensions = [".ps2", ".mcd", ".sav", ".raw", ".bin", ".vmu"]
    valid_exts_lower = [ext.lower() for ext in valid_extensions]

    card_files = [
        f
        for f in target_dir.iterdir()
        if f.is_file() and f.suffix.lower() in valid_exts_lower
    ]

    if not card_files:
        return canonical_file

    # Check if exact canonical name and casing already exists on disk
    exact_match = any(f.name == canonical_card_name for f in card_files)

    if exact_match:
        # Clean up any non-canonical duplicates (e.g. Amplitude (USA).ps2 or Sonic Adventure.bin)
        for f in card_files:
            if f.name != canonical_card_name:
                try:
                    f.unlink()
                    logger.info("Cleaned up redundant local memcard file: %s", f)
                except Exception as e:
                    logger.warning(
                        "Could not delete redundant local memcard file %s: %s",
                        f,
                        e,
                    )
        return canonical_file

    # If canonical file does not exist with exact casing/name:
    # Pick the newest non-canonical card file and rename it
    card_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    primary_card = card_files[0]
    try:
        # If the file differs only in case, rename via temp to avoid collisions on case-insensitive filesystems
        if primary_card.name.lower() == canonical_card_name.lower():
            temp_name = target_dir / f"{canonical_card_name}.tmp_{time.monotonic_ns()}"
            primary_card.rename(temp_name)
            temp_name.rename(canonical_file)
        else:
            primary_card.rename(canonical_file)
        logger.info(
            "Consolidated local memcard %s to canonical filename %s",
            primary_card,
            canonical_file,
        )
    except Exception as e:
        logger.warning(
            "Could not rename %s to %s: %s", primary_card, canonical_file, e
        )

    # Clean up any remaining non-canonical files
    for f in card_files[1:]:
        if f.exists() and f.name != canonical_card_name:
            try:
                f.unlink()
            except Exception as e:
                logger.debug(
                    "Failed removing secondary non-canonical memcard %s: %s",
                    f,
                    e,
                )

    return canonical_file


def get_app_local_memcard_path(
    core_name: str = "",
    rom_stem: str = "",
    card_filename: str = "",
    platform_slug: str = "",
) -> Path:
    """Get path to the app's local memory card file in AppData storage.

    Args:
        core_name: Core identifier string.
        rom_stem: Filename stem of the ROM.
        card_filename: Standardized memory card filename.
        platform_slug: Platform slug.

    Returns:
        Path to the local persistent memory card file.
    """
    sys_folder = get_memcard_system_folder(core_name, platform_slug)
    base_dir = get_default_config_dir() / "memcards" / sys_folder
    game_dir = base_dir / rom_stem

    # Migrate any legacy folder locations if game_dir does not exist
    if not game_dir.exists() and sys_folder == "pcsx2":
        legacy_subdirs = ["playstation-2", "playstation2", "ps2", "sony-playstation-2"]
        for leg in legacy_subdirs:
            leg_dir = get_default_config_dir() / "memcards" / leg / rom_stem
            if leg_dir.is_dir() and any(leg_dir.iterdir()):
                try:
                    game_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(leg_dir), str(game_dir))
                    logger.info(
                        "Migrated legacy memcard directory from %s to %s",
                        leg_dir,
                        game_dir,
                    )
                    break
                except Exception as e:
                    logger.warning(
                        "Could not migrate legacy memcard directory %s: %s",
                        leg_dir,
                        e,
                    )

    game_dir.mkdir(parents=True, exist_ok=True)

    target_name = (
        card_filename
        if card_filename
        else DEFAULT_MEMCARD_FILENAMES.get(sys_folder, "Mcd001.ps2")
    )
    valid_exts = SYSTEM_MEMCARD_EXTENSIONS.get(
        sys_folder, [".ps2", ".mcd", ".sav", ".raw", ".bin", ".vmu"]
    )
    return consolidate_local_memcards(
        game_dir,
        canonical_card_name=target_name,
        valid_extensions=valid_exts,
    )


def get_retroarch_memcard_path(
    configured_retroarch_path: str = "",
    core_name: str = "",
    platform_slug: str = "",
    card_filename: str = "",
) -> Path:
    """Get expected runtime memory card file path inside RetroArch system directory.

    Args:
        configured_retroarch_path: Configured RetroArch binary path.
        core_name: Libretro core identifier.
        platform_slug: Platform slug.
        card_filename: Memory card filename.

    Returns:
        Path to the runtime memory card location.
    """
    sys_folder = get_memcard_system_folder(core_name, platform_slug)
    rel_path = SYSTEM_MEMCARD_REL_PATHS.get(sys_folder, f"{sys_folder}/memcards")
    default_name = DEFAULT_MEMCARD_FILENAMES.get(sys_folder, "Mcd001.ps2")
    target_card_name = card_filename if card_filename else default_name

    # Check RetroArch install folder if portable
    retroarch_exe = RetroArchLauncher.resolve_retroarch_binary(
        configured_retroarch_path
    )
    if retroarch_exe:
        ra_parent = Path(retroarch_exe).parent
        ra_system = ra_parent / "system"
        # Only avoid Program Files if it's the standalone installer (not Steam library)
        is_standalone_program_files = (
            sys.platform == "win32"
            and "program files" in str(ra_parent).lower()
            and "steamapps" not in str(ra_parent).lower()
        )
        is_system_bin = (
            sys.platform != "win32"
            and any(
                p in str(ra_parent).replace("\\", "/").lower()
                for p in ["/usr/bin", "/usr/local/bin", "/bin"]
            )
        )
        if not is_standalone_program_files and not is_system_bin and ra_system.is_dir():
            target_dir = ra_system / rel_path
            target_dir.mkdir(parents=True, exist_ok=True)
            return target_dir / target_card_name

    # Platform default system directories
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming" / "RetroArch" / "system"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "RetroArch" / "system"
    else:
        flatpak_sys = (
            Path.home()
            / ".var"
            / "app"
            / "org.libretro.RetroArch"
            / "config"
            / "retroarch"
            / "system"
        )
        if flatpak_sys.exists() and flatpak_sys.is_dir():
            base = flatpak_sys
        else:
            base = Path.home() / ".config" / "retroarch" / "system"

    target_dir = base / rel_path
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / target_card_name


class SharedMemoryCardStrategy(BaseSaveStrategy):
    """Save strategy for cores/emulators using shared memory card files."""

    name: str = "shared_memory_card"

    def resolve_card_filename(
        self,
        remote_save: Optional[Dict[str, Any]] = None,
        core_name: str = "",
        platform_slug: str = "",
    ) -> str:
        """Determine memory card filename from platform defaults.

        Args:
            remote_save: Optional remote save metadata dictionary.
            core_name: Libretro core identifier.
            platform_slug: Platform identifier slug.

        Returns:
            Resolved memory card filename string.
        """
        sys_folder = get_memcard_system_folder(core_name, platform_slug)
        default_name = DEFAULT_MEMCARD_FILENAMES.get(sys_folder, "Mcd001.ps2")

        if sys_folder == "pcsx2":
            # PS2 memory cards for Slot 1 MUST strictly be named 'Mcd001.ps2'.
            # Normalize all non-canonical names (e.g. Amplitude (USA).ps2, mcd001.ps2, Mcd002.ps2)
            # strictly to 'Mcd001.ps2' to guarantee core recognition and case compatibility.
            return "Mcd001.ps2"

        if sys_folder == "dc":
            if remote_save:
                r_name = remote_save.get("name") or remote_save.get("file_name") or ""
                if r_name and r_name.lower().startswith("vmu_save_"):
                    # Preserve slot specification, e.g. vmu_save_A2.bin
                    prefix = "vmu_save_"
                    suffix_part = r_name[len(prefix):]
                    return f"{prefix}{suffix_part}"
            return "vmu_save_A1.bin"

        if remote_save:
            r_name = remote_save.get("name") or remote_save.get("file_name") or ""
            if (
                r_name
                and (
                    r_name.lower().startswith("vmu_save_")
                    or r_name.lower() in [
                        "mcd001.ps2",
                        "mcd002.ps2",
                        "mcd001.mcd",
                        "mcd002.mcd",
                    ]
                )
                and Path(r_name).suffix.lower()
                in [".bin", ".vmu", ".ps2", ".mcd", ".raw", ".sav"]
            ):
                return r_name
        return default_name

    def find_local_save_file(
        self,
        rom_path: str,
        platform_slug: str = "",
        configured_retroarch_path: str = "",
        remote_ext: str = "",
        core_name: str = "",
        **kwargs: Any,
    ) -> Tuple[Optional[Path], Path]:
        """Locate local memory card file and default RetroArch runtime destination.

        Args:
            rom_path: Path to ROM.
            platform_slug: Platform slug.
            configured_retroarch_path: Configured RetroArch path.
            remote_ext: Extension of remote save.
            core_name: Libretro core identifier.
            **kwargs: Extra parameters.

        Returns:
            Tuple of (existing_local_app_card_or_none, runtime_retroarch_card_path).
        """
        rom_p = Path(rom_path)
        rom_stem = rom_p.stem
        sys_folder = get_memcard_system_folder(core_name, platform_slug)
        default_card = DEFAULT_MEMCARD_FILENAMES.get(sys_folder, "Mcd001.ps2")
        card_filename = (
            f"{default_card.rsplit('.', 1)[0]}.{remote_ext.lstrip('.')}"
            if remote_ext
            else default_card
        )
        local_app_card = get_app_local_memcard_path(
            core_name, rom_stem, card_filename, platform_slug
        )
        ra_card = get_retroarch_memcard_path(
            configured_retroarch_path, core_name, platform_slug, card_filename
        )

        if local_app_card.exists():
            return local_app_card, ra_card
        return None, ra_card

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
        """Perform pre-launch save sync evaluation and card swap.

        Args:
            rom_id: RomM identifier of the game.
            rom_path: Path to ROM file.
            platform_slug: Platform slug.
            client: RomMApiClient instance.
            configured_retroarch_path: Configured RetroArch path.
            slot: Target save slot.
            core_name: Libretro core identifier.
            **kwargs: Extra parameters.

        Returns:
            Tuple of (action, message, remote_save, retroarch_card_file).
        """
        rom_p = Path(rom_path)
        rom_stem = rom_p.stem

        logger.info(
            "Executing pre-launch save sync [shared_memory_card] for rom_id %s (platform: %s, slot: %s, core: %s)",
            rom_id,
            platform_slug,
            slot,
            core_name,
        )

        remote_saves = []
        try:
            remote_saves = client.get_saves(rom_id, slot=slot)
        except Exception as e:
            logger.warning(
                "Could not fetch remote saves from RomM for rom_id %s: %s",
                rom_id,
                e,
            )

        remote_save = remote_saves[0] if remote_saves else None
        card_filename = self.resolve_card_filename(
            remote_save, core_name=core_name, platform_slug=platform_slug
        )

        local_card_file = get_app_local_memcard_path(
            core_name, rom_stem, card_filename, platform_slug
        )
        ra_card_file = get_retroarch_memcard_path(
            configured_retroarch_path, core_name, platform_slug, card_filename
        )

        local_exists = local_card_file.exists()
        local_hash = (
            calculate_save_hash(str(local_card_file)) if local_exists else None
        )
        local_mtime = local_card_file.stat().st_mtime if local_exists else None
        local_size = local_card_file.stat().st_size if local_exists else None
        (
            last_sync_hash,
            last_sync_server_hash,
            last_sync_local_size,
        ) = self._load_baseline(rom_id, local_card_file.name)

        # Freshness is evaluated STRICTLY between App local storage card and RomM remote save
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
            "Evaluated pre-launch shared memcard action: %s for rom_id %s (local_exists: %s, file: %s)",
            action,
            rom_id,
            local_exists,
            local_card_file,
        )

        def _record_baseline() -> None:
            """Record latest memory card baseline into database."""
            BaseSaveStrategy._record_baseline(
                self, rom_id, local_card_file, slot=slot, remote_save=remote_save
            )

        def _clean_ra_memcard_dir() -> None:
            """Clean RetroArch system memory card directory before swapping in game card."""
            ra_memcard_dir = ra_card_file.parent
            sys_folder = get_memcard_system_folder(core_name, platform_slug)
            valid_exts = SYSTEM_MEMCARD_EXTENSIONS.get(
                sys_folder, [".ps2", ".mcd", ".sav", ".raw", ".bin", ".vmu"]
            )

            if ra_memcard_dir.exists():
                for f in ra_memcard_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in valid_exts:
                        if sys_folder == "dc":
                            # Strictly target VMU files only (e.g. vmu_save_A1.bin), NEVER BIOS files like dc_boot.bin / dc_flash.bin
                            if (
                                f.name.lower().startswith("vmu_save_")
                                or f.suffix.lower() == ".vmu"
                                or f.name.lower() == card_filename.lower()
                            ):
                                try:
                                    f.unlink()
                                except Exception as e:
                                    logger.warning(
                                        "Could not remove stale RetroArch VMU file %s: %s",
                                        f,
                                        e,
                                    )
                        else:
                            try:
                                f.unlink()
                            except Exception as e:
                                logger.warning(
                                    "Could not remove stale RetroArch memcard %s: %s",
                                    f,
                                    e,
                                )

        if action == "DOWNLOAD" and remote_save:
            save_id = remote_save.get("id")
            if save_id:
                if local_exists:
                    quarantine_local_save(str(local_card_file))

                # 1. Download directly to app local storage
                success = client.download_save_content(
                    save_id, str(local_card_file)
                )
                if success:
                    # 2. Swap to RetroArch system directory
                    _clean_ra_memcard_dir()
                    shutil.copy2(local_card_file, ra_card_file)
                    _record_baseline()
                    logger.info(
                        "Downloaded save from RomM and staged to RetroArch: %s",
                        ra_card_file,
                    )
                    return (
                        "DOWNLOAD",
                        "Downloaded latest memory card from RomM.",
                        remote_save,
                        ra_card_file,
                    )
                logger.error(
                    "Failed to download save content (save_id %s) from RomM",
                    save_id,
                )
                return (
                    "ERROR",
                    "Failed to download memory card from RomM.",
                    remote_save,
                    ra_card_file,
                )

        if action == "UPLOAD" and local_exists:
            try:
                save_id = remote_save.get("id") if remote_save else None
                res = client.upload_save(
                    rom_id, str(local_card_file), save_id=save_id, slot=slot
                )
                if isinstance(res, dict) and res.get("content_hash"):
                    remote_save = res
                _clean_ra_memcard_dir()
                shutil.copy2(local_card_file, ra_card_file)
                _record_baseline()
                return (
                    "UPLOAD",
                    "Uploaded local memory card to RomM.",
                    remote_save,
                    ra_card_file,
                )
            except Exception as e:
                logger.error("Failed to upload memory card to RomM: %s", e)
                if local_card_file.exists():
                    _clean_ra_memcard_dir()
                    shutil.copy2(local_card_file, ra_card_file)
                return (
                    "ERROR",
                    f"Failed to upload memory card: {e}",
                    remote_save,
                    ra_card_file,
                )

        if action == "NO_OP":
            if local_card_file.exists():
                _clean_ra_memcard_dir()
                shutil.copy2(local_card_file, ra_card_file)
            _record_baseline()
            return (
                "NO_OP",
                "Memory card is up to date.",
                remote_save,
                ra_card_file,
            )

        if action == "CONFLICT":
            return (
                "CONFLICT",
                "Memory card conflict detected.",
                remote_save,
                local_card_file,
            )

        # Offline fallback: if local_card_file exists, swap to RetroArch
        if local_card_file.exists():
            _clean_ra_memcard_dir()
            shutil.copy2(local_card_file, ra_card_file)
            _record_baseline()
            logger.info(
                "Offline launch: swapped local memory card %s to RetroArch %s",
                local_card_file,
                ra_card_file,
            )

        return (
            action,
            "Shared memory card pre-launch complete.",
            remote_save,
            ra_card_file,
        )

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
            platform_slug: Platform identifier slug.
            configured_retroarch_path: Configured RetroArch path.
            rom_path: Path to ROM.
            core_name: Libretro core identifier.
            **kwargs: Extra parameters.

        Returns:
            Tuple of (success_boolean, message).
        """
        effective_rom_path = rom_path if rom_path else save_path
        rom_p = Path(effective_rom_path)
        rom_stem = rom_p.stem
        if (
            rom_stem.lower() in ["mcd001", "mcd002", "vmu_save_a1", "vmu_save_a2"]
            and rom_path
        ):
            rom_stem = Path(rom_path).stem

        sys_folder = get_memcard_system_folder(core_name, platform_slug)
        card_filename = self.resolve_card_filename(
            core_name=core_name, platform_slug=platform_slug
        )
        ra_card_file = get_retroarch_memcard_path(
            configured_retroarch_path, core_name, platform_slug, card_filename
        )
        ra_memcard_dir = ra_card_file.parent
        valid_exts = SYSTEM_MEMCARD_EXTENSIONS.get(
            sys_folder, [".ps2", ".mcd", ".sav", ".raw", ".bin", ".vmu"]
        )

        save_p = Path(save_path)
        if (
            not ra_card_file.exists()
            and save_p.exists()
            and save_p.suffix.lower() in valid_exts
        ):
            if (
                sys_folder != "dc"
                or save_p.name.lower().startswith("vmu_save_")
                or save_p.suffix.lower() == ".vmu"
            ):
                ra_card_file = save_p

        # If primary card file doesn't exist directly, check if any matching card file exists in ra_memcard_dir
        if not ra_card_file.exists() and ra_memcard_dir.exists():
            for f in ra_memcard_dir.iterdir():
                if f.is_file() and f.suffix.lower() in valid_exts:
                    if sys_folder == "dc":
                        if (
                            f.name.lower().startswith("vmu_save_")
                            or f.suffix.lower() == ".vmu"
                        ):
                            ra_card_file = f
                            break
                    else:
                        ra_card_file = f
                        break

        if not ra_card_file.exists():
            logger.info(
                "No RetroArch memory card file found in %s post-launch to upload.",
                ra_memcard_dir,
            )
            return True, "No local RetroArch memory card found post-launch."

        local_card_file = get_app_local_memcard_path(
            core_name, rom_stem, ra_card_file.name, platform_slug
        )

        # 1. Update app local storage with newly saved RetroArch card
        try:
            shutil.copy2(ra_card_file, local_card_file)
            logger.info(
                "Copied post-launch RetroArch memory card %s back to app local storage %s",
                ra_card_file,
                local_card_file,
            )
        except Exception as e:
            logger.error(
                "Failed to copy RetroArch memory card to app local storage: %s", e
            )
            return False, f"Failed to update local memory card storage: {e}"

        # 2. Upload updated memory card to RomM
        upload_success = True
        remote_save = None
        try:
            save_id, remote_save = self._match_remote_save(
                client, rom_id, local_card_file, slot=slot
            )
            res = client.upload_save(
                rom_id, str(local_card_file), save_id=save_id, slot=slot
            )
            if isinstance(res, dict) and res.get("content_hash"):
                remote_save = res

            self._record_baseline(
                rom_id, local_card_file, slot=slot, remote_save=remote_save
            )
            logger.info(
                "Successfully uploaded memory card %s (slot: %s) to RomM post-launch.",
                local_card_file.name,
                slot,
            )
        except Exception as e:
            upload_success = False
            logger.warning(
                "Post-launch memory card upload to RomM encountered error for rom_id %s: %s",
                rom_id,
                e,
            )

        # 3. Clean up RetroArch memory cards with retry loop to allow Windows process locks to release

        cards_to_delete: List[Path] = []
        if ra_memcard_dir.exists():
            for f in ra_memcard_dir.iterdir():
                if f.is_file() and f.suffix.lower() in valid_exts:
                    if sys_folder == "dc":
                        # Strictly target VMU files only (e.g. vmu_save_A1.bin), NEVER BIOS files like dc_boot.bin / dc_flash.bin
                        if (
                            f.name.lower().startswith("vmu_save_")
                            or f.suffix.lower() == ".vmu"
                            or f.name.lower() == card_filename.lower()
                        ):
                            cards_to_delete.append(f)
                    else:
                        cards_to_delete.append(f)
        if ra_card_file.exists() and ra_card_file not in cards_to_delete:
            if (
                sys_folder != "dc"
                or ra_card_file.name.lower().startswith("vmu_save_")
                or ra_card_file.suffix.lower() == ".vmu"
                or ra_card_file.name.lower() == card_filename.lower()
            ):
                cards_to_delete.append(ra_card_file)

        for c_file in cards_to_delete:
            deleted = False
            for attempt in range(5):
                try:
                    if c_file.exists():
                        c_file.unlink()
                    deleted = True
                    logger.info(
                        "Deleted RetroArch memory card file %s post-launch to maintain clean state",
                        c_file,
                    )
                    break
                except PermissionError:
                    logger.debug(
                        "PermissionError unlinking %s (attempt %d/5), pausing 0.2s for process lock release...",
                        c_file,
                        attempt + 1,
                    )
                    time.sleep(0.2)
                except Exception as e:
                    logger.warning(
                        "Failed to delete RetroArch memory card file %s post-launch: %s",
                        c_file,
                        e,
                    )
                    break

        if upload_success:
            return (
                True,
                f"Successfully uploaded memory card ({local_card_file.name}) to RomM.",
            )
        return (
            True,
            f"Saved memory card locally to app storage ({local_card_file.name}); RomM upload skipped/failed.",
        )
