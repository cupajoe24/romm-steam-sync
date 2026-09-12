"""Dolphin core and GameCube memory card handler implementation."""

import logging
import os
from pathlib import Path
import re
import shutil
from typing import Any, Dict, List, Optional

from romm_steam_sync.adapters.retroarch_launcher import RetroArchLauncher
from romm_steam_sync.service_layer.save_strategies.handlers.base import (
    sanitize_filename,
)
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin import (
    BaseDolphinHandler,
    REGION_CHAR_MAP,
    REGION_TAG_PATTERNS,
    SUPPORTED_REGIONS,
    _GC_MAGIC,
    read_disc_container_header,
)

logger = logging.getLogger(__name__)


def read_gc_container_header(file_path: Path) -> Optional[Dict[str, Any]]:
    """Extract GameCube disc header across container variations (ISO, GCM, RVZ, WIA, CISO, GCZ, TGC).

    Args:
        file_path: Filesystem path to GameCube ROM file.

    Returns:
        Extracted metadata dictionary if valid header found, or None.
    """
    return read_disc_container_header(
        file_path=file_path,
        magic=_GC_MAGIC,
        magic_offset=0x1C,
        is_wii=False,
    )


def read_gci_header(file_path: Path) -> Optional[Dict[str, str]]:
    """Parse GameCode, MakerCode, and internal filename from a GameCube .gci save header.

    Args:
        file_path: Path to .gci save file.

    Returns:
        Dictionary of extracted GCI fields if valid, or None.
    """
    try:
        if not file_path.is_file() or file_path.stat().st_size < 0x28:
            return None

        with open(file_path, "rb") as f:
            header = f.read(0x28)

        if len(header) < 0x28:
            return None

        raw_game_code = header[0:4].decode("latin1", errors="ignore")
        raw_maker_code = header[4:6].decode("latin1", errors="ignore")
        raw_name = (
            header[8:0x28]
            .split(b"\x00")[0]
            .decode("latin1", errors="ignore")
            .strip()
        )

        if raw_game_code:
            return {
                "game_code": raw_game_code,
                "maker_code": raw_maker_code,
                "internal_name": raw_name,
            }
    except Exception as e:
        logger.debug("Failed reading GCI header for %s: %s", file_path, e)
        return None

    return None


class DolphinGameCubeHandler(BaseDolphinHandler):
    """Platform handler for Dolphin emulator / libretro core GameCube memory card management."""

    def extract_rom_metadata(self, rom_path: str) -> Dict[str, Any]:
        """Extract GameCode, MakerCode, Region, Title, Disc Number/Version from GameCube ROM disc header or filename.

        Args:
            rom_path: Path to the GameCube ROM file.

        Returns:
            Dictionary containing extracted disc metadata.
        """
        metadata: Dict[str, Any] = {
            "game_code": "",
            "maker_code": "",
            "region": "USA",
            "title": "",
            "valid_header": False,
            "disc_number": 0,
            "disc_version": 0,
        }

        rom_p = Path(rom_path)
        if not rom_path:
            return metadata

        # 1. Try reading disc container header across ISO, GCM, RVZ, WIA, CISO, GCZ, TGC
        if rom_p.is_file():
            hdr_meta = read_gc_container_header(rom_p)
            if hdr_meta:
                metadata.update(hdr_meta)

        # 2. Fallback to filename tag parsing for region and gamecode if header extraction was incomplete
        filename_str = rom_p.stem
        if not metadata["game_code"]:
            game_id_match = re.search(r"\[([A-Z0-9]{4,6})\]", filename_str)
            if game_id_match:
                extracted_id = game_id_match.group(1)
                metadata["game_code"] = extracted_id[:4]
                if len(extracted_id) >= 6:
                    metadata["maker_code"] = extracted_id[4:6]
                if len(metadata["game_code"]) >= 4:
                    region_char = metadata["game_code"][3].upper()
                    if region_char in REGION_CHAR_MAP:
                        metadata["region"] = REGION_CHAR_MAP[region_char]

        # Check filename tags for region if not set by valid disc header
        if not metadata["valid_header"]:
            detected_region = self.detect_region_from_tags(filename_str)
            if detected_region:
                metadata["region"] = detected_region

        if not metadata["title"]:
            metadata["title"] = sanitize_filename(filename_str)

        return metadata

    def get_save_directories(
        self,
        configured_retroarch_path: str = "",
        rom_path: str = "",
        platform_slug: str = "",
    ) -> List[Path]:
        """Resolve candidate save directories for RetroArch Dolphin core (User/GC/<Region>/Card A).

        Args:
            configured_retroarch_path: Configured RetroArch path.
            rom_path: Path to ROM.
            platform_slug: Platform slug.

        Returns:
            List of candidate save directories.
        """
        meta = self.extract_rom_metadata(rom_path)
        primary_region = meta.get("region") or "USA"

        base_save_dirs = self.get_base_save_directories(
            configured_retroarch_path=configured_retroarch_path
        )

        candidate_dirs: List[Path] = []

        # Region ordering: Primary detected region first, then remaining supported regions
        region_order = [primary_region] + [
            r for r in SUPPORTED_REGIONS if r != primary_region
        ]

        # For each base save directory, construct Dolphin User/GC hierarchies
        for base_dir in base_save_dirs:
            for reg in region_order:
                # Primary: dolphin-emu/User/GC/<Region>/Card A
                candidate_dirs.append(
                    base_dir / "dolphin-emu" / "User" / "GC" / reg / "Card A"
                )
                # Fallback: User/GC/<Region>/Card A
                candidate_dirs.append(base_dir / "User" / "GC" / reg / "Card A")
                # Fallback slot: dolphin-emu/User/GC/<Region>/Card B
                candidate_dirs.append(
                    base_dir / "dolphin-emu" / "User" / "GC" / reg / "Card B"
                )

        return candidate_dirs

    def get_legacy_save_directories(
        self,
        configured_retroarch_path: str = "",
        rom_path: str = "",
    ) -> List[Path]:
        """Resolve legacy non-Card A directories (e.g. next to ROM or base saves) for migration.

        Args:
            configured_retroarch_path: Configured RetroArch binary path.
            rom_path: Path to ROM.

        Returns:
            List of legacy directories to scan.
        """
        legacy_dirs: List[Path] = []
        if rom_path:
            legacy_dirs.append(Path(rom_path).parent)

        legacy_dirs.extend(
            self.get_base_save_directories(
                configured_retroarch_path=configured_retroarch_path
            )
        )

        return legacy_dirs

    def resolve_target_save_path(
        self,
        save_dirs: List[Path],
        rom_path: str,
        remote_filename: str = "",
        remote_ext: str = "",
        platform_slug: str = "",
    ) -> Path:
        """Determine default target path to place/download the GameCube save file in Card A.

        Args:
            save_dirs: Candidate save directories.
            rom_path: Path to ROM file.
            remote_filename: Optional remote filename.
            remote_ext: Optional remote extension.
            platform_slug: Platform slug.

        Returns:
            Target destination Path in Card A directory.
        """
        # Find first existing or primary Card A directory
        primary_dir = None
        for d in save_dirs:
            if d.exists() and "card a" in str(d).lower():
                primary_dir = d
                break

        if not primary_dir:
            primary_dir = (
                save_dirs[0]
                if save_dirs
                else Path.home()
                / "AppData"
                / "Roaming"
                / "RetroArch"
                / "saves"
                / "dolphin-emu"
                / "User"
                / "GC"
                / "USA"
                / "Card A"
            )

        if remote_filename:
            return primary_dir / remote_filename

        meta = self.extract_rom_metadata(rom_path)
        game_code = meta.get("game_code") or ""
        maker_code = meta.get("maker_code") or "01"
        raw_title = meta.get("title") or (
            Path(rom_path).stem if rom_path else "game"
        )
        clean_title = sanitize_filename(raw_title)

        if game_code:
            target_name = f"{maker_code}-{game_code}-{clean_title}.gci"
        else:
            ext = f".{remote_ext.lstrip('.')}" if remote_ext else ".gci"
            target_name = f"{clean_title}{ext}"

        return primary_dir / target_name

    def find_existing_save(
        self,
        save_dirs: List[Path],
        rom_path: str,
        remote_filename: str = "",
        remote_ext: str = "",
        platform_slug: str = "",
    ) -> Optional[Path]:
        """Find an existing save file matching this game in Card A (or migrate from legacy locations).

        Args:
            save_dirs: Candidate Card A directories.
            rom_path: Path to ROM.
            remote_filename: Optional remote save filename.
            remote_ext: Optional remote save extension.
            platform_slug: Platform slug.

        Returns:
            Path to existing save file or None.
        """
        meta = self.extract_rom_metadata(rom_path)
        game_code = meta.get("game_code") or ""

        rom_p = Path(rom_path) if rom_path else None
        rom_stem = rom_p.stem if rom_p else ""

        stems_to_try: List[str] = []
        disc_stripped = ""
        if rom_stem:
            stems_to_try.append(rom_stem)
            if "_" in rom_stem:
                prefix, rest = rom_stem.split("_", 1)
                if prefix.isdigit() and rest:
                    stems_to_try.append(rest)
            # Multi-disc handling: Strip (Disc 1)/(Disc 2) tags so all discs link to shared save
            disc_stripped = re.sub(
                r"\s*\((?:Disc|Disk|CD)\s*\d+\)",
                "",
                rom_stem,
                flags=re.IGNORECASE,
            ).strip()
            if disc_stripped and disc_stripped not in stems_to_try:
                stems_to_try.append(disc_stripped)

        save_extensions = [".gci", ".raw", ".sav", ".srm", ".gcp"]
        if remote_ext:
            clean_ext = f".{remote_ext.lstrip('.')}"
            if clean_ext not in save_extensions:
                save_extensions.insert(0, clean_ext)

        clean_rom_stem = self.clean_string_for_matching(disc_stripped or rom_stem)
        clean_meta_title = self.clean_string_for_matching(meta.get("title", ""))

        # 1. Search strictly inside designated core Card A / Card B directories first
        for s_dir in save_dirs:
            if not s_dir.exists() or not s_dir.is_dir():
                continue

            # A. Exact remote filename match
            if remote_filename:
                cand = s_dir / remote_filename
                if cand.is_file():
                    return cand

            try:
                dir_files = [f for f in s_dir.iterdir() if f.is_file()]
            except Exception as e:
                logger.debug("Failed listing directory %s: %s", s_dir, e)
                continue

            # B. Match by GCI internal header GameCode
            if game_code:
                for f in dir_files:
                    if f.suffix.lower() == ".gci":
                        gci_meta = read_gci_header(f)
                        if (
                            gci_meta
                            and gci_meta.get("game_code", "").upper()
                            == game_code.upper()
                        ):
                            return f

                # C. Match by GameCode pattern in filename (e.g. 01-GALE-Melee.gci or GALE01.raw)
                for f in dir_files:
                    if game_code.lower() in f.name.lower():
                        return f

            # D. Match by normalized title against GCI internal name or filename
            for f in dir_files:
                f_clean = self.clean_string_for_matching(f.stem)
                if (
                    clean_rom_stem
                    and len(clean_rom_stem) >= 4
                    and clean_rom_stem in f_clean
                ):
                    return f
                if (
                    clean_meta_title
                    and len(clean_meta_title) >= 4
                    and clean_meta_title in f_clean
                ):
                    return f
                if f.suffix.lower() == ".gci":
                    gci_meta = read_gci_header(f)
                    if gci_meta:
                        int_clean = self.clean_string_for_matching(
                            gci_meta.get("internal_name", "")
                        )
                        if int_clean and len(int_clean) >= 4:
                            if (
                                clean_rom_stem and int_clean in clean_rom_stem
                            ) or (
                                clean_meta_title and int_clean in clean_meta_title
                            ):
                                return f

            # E. Match by ROM stems
            for stem in stems_to_try:
                for ext in save_extensions:
                    for f in dir_files:
                        if f.name.lower() == f"{stem}{ext}".lower():
                            return f

        # 2. Check for legacy saves (e.g. next to ROM or root saves) to migrate into Card A
        legacy_dirs = self.get_legacy_save_directories(rom_path=rom_path)
        for l_dir in legacy_dirs:
            if not l_dir.exists() or not l_dir.is_dir():
                continue

            legacy_cand: Optional[Path] = None
            if remote_filename:
                cand = l_dir / remote_filename
                if cand.is_file():
                    legacy_cand = cand

            if not legacy_cand:
                try:
                    dir_files = [f for f in l_dir.iterdir() if f.is_file()]
                except Exception as e:
                    logger.debug(
                        "Failed listing legacy directory %s: %s", l_dir, e
                    )
                    continue

                if game_code:
                    for f in dir_files:
                        if f.suffix.lower() == ".gci":
                            gci_meta = read_gci_header(f)
                            if (
                                gci_meta
                                and gci_meta.get("game_code", "").upper()
                                == game_code.upper()
                            ):
                                legacy_cand = f
                                break

                if not legacy_cand:
                    for stem in stems_to_try:
                        for ext in save_extensions:
                            for f in dir_files:
                                if f.name.lower() == f"{stem}{ext}".lower():
                                    legacy_cand = f
                                    break
                            if legacy_cand:
                                break
                        if legacy_cand:
                            break

            if legacy_cand and legacy_cand.is_file():
                # Migrate legacy save file into primary Card A destination
                target_dest = self.resolve_target_save_path(
                    save_dirs=save_dirs,
                    rom_path=rom_path,
                    remote_filename=remote_filename or legacy_cand.name,
                    remote_ext=remote_ext or legacy_cand.suffix,
                    platform_slug=platform_slug,
                )
                try:
                    target_dest.parent.mkdir(parents=True, exist_ok=True)
                    if legacy_cand.resolve() != target_dest.resolve():
                        shutil.move(str(legacy_cand), str(target_dest))
                        logger.info(
                            "Migrated legacy GameCube save from %s to %s",
                            legacy_cand,
                            target_dest,
                        )
                    return target_dest
                except Exception as e:
                    logger.warning(
                        "Failed migrating legacy save %s: %s", legacy_cand, e
                    )
                    return legacy_cand

        return None
