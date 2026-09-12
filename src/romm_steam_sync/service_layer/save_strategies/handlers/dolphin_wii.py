"""Dolphin core and standalone Dolphin Nintendo Wii save handler implementation."""

import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import zipfile

from romm_steam_sync.adapters.retroarch_launcher import RetroArchLauncher
from romm_steam_sync.service_layer.save_strategies.handlers.base import (
    sanitize_filename,
)
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin import (
    BaseDolphinHandler,
    REGION_CHAR_MAP,
    _WII_MAGIC,
    read_disc_container_header,
)

logger = logging.getLogger(__name__)

# Regex pattern to detect Game ID / Title ID from filename tags (e.g. [RMCE01] or [00010000524D4345])
WII_GAME_ID_PATTERN = re.compile(
    r"\[([A-Z0-9]{4,6}|00010000[0-9a-fA-F]{8})\]", re.IGNORECASE
)


def read_wii_disc_header(file_path: Path) -> Optional[Dict[str, Any]]:
    """Extract Wii disc header across container variations (ISO, WBFS, RVZ, WIA, CISO, GCZ).

    Args:
        file_path: Filesystem path to Wii ROM file.

    Returns:
        Extracted metadata dictionary if valid header found, or None.
    """
    return read_disc_container_header(
        file_path=file_path,
        magic=_WII_MAGIC,
        magic_offset=0x18,
        is_wii=True,
    )


def consolidate_wii_save_directory(data_dir: Path, target_zip: Path) -> Path:
    """Bundle Wii emulated NAND save directory files into a deterministic zip archive.

    Args:
        data_dir: Directory containing Wii save files (e.g. title/00010000/<tid>/data).
        target_zip: Destination zip path.

    Returns:
        Path to the created or updated zip archive.
    """
    save_files = [
        f
        for f in data_dir.iterdir()
        if f.is_file()
        and not f.name.startswith(".")
        and not f.name.endswith(".tmp")
        and not f.name.endswith(".zip")
    ]

    target_zip.parent.mkdir(parents=True, exist_ok=True)
    needs_update = not target_zip.exists()
    if not needs_update:
        zip_mtime = target_zip.stat().st_mtime
        if any(f.stat().st_mtime > zip_mtime for f in save_files):
            needs_update = True

    if needs_update:
        with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(save_files, key=lambda x: x.name):
                zf.write(f, arcname=f.name)
        logger.debug(
            "Consolidated %d Wii save files from %s into %s",
            len(save_files),
            data_dir,
            target_zip,
        )

    return target_zip


def unpack_wii_save_archive(zip_path: Path, dest_data_dir: Path) -> None:
    """Unpack Wii save archive contents safely into the destination NAND data folder.

    Args:
        zip_path: Path to the downloaded .zip save archive.
        dest_data_dir: Target data directory (e.g. title/00010000/<tid>/data).
    """
    if not zip_path.is_file() or not zipfile.is_zipfile(zip_path):
        return

    dest_data_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            target_p = (dest_data_dir / member.filename).resolve()
            if not str(target_p).startswith(str(dest_data_dir.resolve())):
                continue
            if member.is_dir():
                target_p.mkdir(parents=True, exist_ok=True)
            else:
                target_p.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target_p, "wb") as dst:
                    dst.write(src.read())
    logger.info("Unpacked Wii save archive %s into %s", zip_path.name, dest_data_dir)


class DolphinWiiHandler(BaseDolphinHandler):
    """Save handler for Nintendo Wii games using Dolphin libretro core and standalone Dolphin."""

    def extract_rom_metadata(self, rom_path: str) -> Dict[str, Any]:
        """Extract GameCode, Title ID, MakerCode, Region, and Title from Wii ROM header or filename.

        Args:
            rom_path: Path to the Wii ROM file.

        Returns:
            Dictionary containing extracted disc metadata.
        """
        metadata: Dict[str, Any] = {
            "game_code": "",
            "title_id_low": "",
            "title_id": "",
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

        # 1. Try reading disc container header across ISO, WBFS, RVZ, WIA, CISO, GCZ
        if rom_p.is_file():
            hdr_meta = read_wii_disc_header(rom_p)
            if hdr_meta:
                metadata.update(hdr_meta)

        filename_str = rom_p.stem
        # 2. Fallback to filename tag parsing if header extraction was unavailable
        if not metadata["game_code"]:
            game_id_match = WII_GAME_ID_PATTERN.search(filename_str)
            if game_id_match:
                extracted_id = game_id_match.group(1)
                if extracted_id.upper().startswith("00010000") and len(extracted_id) == 16:
                    metadata["title_id"] = extracted_id.upper()
                    metadata["title_id_low"] = extracted_id[8:].lower()
                    try:
                        ascii_code = bytes.fromhex(extracted_id[8:]).decode("latin1", errors="ignore")
                        metadata["game_code"] = ascii_code
                    except Exception:
                        metadata["game_code"] = extracted_id[8:12]
                else:
                    metadata["game_code"] = extracted_id[:4]
                    if len(extracted_id) >= 6:
                        metadata["maker_code"] = extracted_id[4:6]
                    metadata["title_id_low"] = metadata["game_code"].encode("latin1").hex().lower()
                    metadata["title_id"] = f"00010000{metadata['title_id_low'].upper()}"

                if len(metadata["game_code"]) >= 4:
                    region_char = metadata["game_code"][3].upper()
                    if region_char in REGION_CHAR_MAP:
                        metadata["region"] = REGION_CHAR_MAP[region_char]
                metadata["valid_header"] = bool(metadata["game_code"])

        # Region fallback check
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
        """Resolve candidate save directories for Dolphin Wii emulated NAND.

        Args:
            configured_retroarch_path: Configured RetroArch path.
            rom_path: Path to ROM.
            platform_slug: Platform identifier slug.

        Returns:
            List of candidate save directories.
        """
        candidate_dirs: List[Path] = []
        base_roots_to_scan = self.get_base_save_directories(
            configured_retroarch_path=configured_retroarch_path
        )

        # 1. Configured RetroArch binary directory
        ra_exe = RetroArchLauncher.resolve_retroarch_binary(
            configured_retroarch_path
        )
        if ra_exe:
            exe_parent = Path(ra_exe).parent
            saves_p = exe_parent / "saves"
            candidate_dirs.extend([
                saves_p / "dolphin-emu" / "User" / "Wii" / "title" / "00010000",
                saves_p / "User" / "Wii" / "title" / "00010000",
                saves_p / "dolphin-emu" / "User" / "Wii",
                saves_p / "User" / "Wii",
                exe_parent / "system" / "dolphin-emu" / "User" / "Wii" / "title" / "00010000",
            ])

        # 2. Standard user home and platform directories
        home = Path.home()
        if os.name == "nt":
            appdata = (
                Path(os.environ.get("APPDATA", ""))
                if os.environ.get("APPDATA")
                else home / "AppData" / "Roaming"
            )
            ra_saves = appdata / "RetroArch" / "saves"

            candidate_dirs.extend([
                # RetroArch Windows paths
                ra_saves / "dolphin-emu" / "User" / "Wii" / "title" / "00010000",
                ra_saves / "User" / "Wii" / "title" / "00010000",
                Path(r"C:\RetroArch-Win64\saves\dolphin-emu\User\Wii\title\00010000"),
                Path(r"C:\Program Files\RetroArch-Win64\saves\dolphin-emu\User\Wii\title\00010000"),
                # Standalone Dolphin Windows paths
                home / "Documents" / "Dolphin Emulator" / "Wii" / "title" / "00010000",
                appdata / "Dolphin Emulator" / "Wii" / "title" / "00010000",
            ])
        else:
            ra_saves = home / ".config" / "retroarch" / "saves"
            flatpak_ra_saves = (
                home
                / ".var"
                / "app"
                / "org.libretro.RetroArch"
                / "config"
                / "retroarch"
                / "saves"
            )

            candidate_dirs.extend([
                # Linux Native RetroArch
                ra_saves / "dolphin-emu" / "User" / "Wii" / "title" / "00010000",
                ra_saves / "User" / "Wii" / "title" / "00010000",
                # Linux Flatpak RetroArch
                flatpak_ra_saves / "dolphin-emu" / "User" / "Wii" / "title" / "00010000",
                flatpak_ra_saves / "User" / "Wii" / "title" / "00010000",
                # RetroDECK
                home
                / ".var"
                / "app"
                / "net.retrodeck.retrodeck"
                / "config"
                / "retrodeck"
                / "saves"
                / "dolphin-emu"
                / "User"
                / "Wii"
                / "title"
                / "00010000",
                # Standalone Dolphin Linux
                home / ".local" / "share" / "dolphin-emu" / "Wii" / "title" / "00010000",
                home
                / ".var"
                / "app"
                / "org.DolphinEmu.dolphin-emu"
                / "data"
                / "dolphin-emu"
                / "Wii"
                / "title"
                / "00010000",
                # macOS
                home
                / "Library"
                / "Application Support"
                / "RetroArch"
                / "saves"
                / "dolphin-emu"
                / "User"
                / "Wii"
                / "title"
                / "00010000",
                home
                / "Library"
                / "Application Support"
                / "Dolphin"
                / "Wii"
                / "title"
                / "00010000",
            ])

        # 3. Dynamic scan of base save roots for existing 'Wii/title/00010000'
        for b_root in base_roots_to_scan:
            if b_root.exists() and b_root.is_dir():
                try:
                    for found in b_root.rglob("00010000"):
                        if found.is_dir() and "wii" in str(found).lower():
                            candidate_dirs.insert(0, found)
                except Exception as e:
                    logger.debug("Error scanning base root %s for Wii NAND: %s", b_root, e)

        # 4. Content directory next to ROM
        if rom_path:
            p_rom = Path(rom_path)
            candidate_dirs.append(
                p_rom.parent / "dolphin-emu" / "User" / "Wii" / "title" / "00010000"
            )
            candidate_dirs.append(p_rom.parent)

        # Deduplicate while preserving priority order
        seen = set()
        unique_dirs: List[Path] = []
        for d in candidate_dirs:
            norm = str(d).lower()
            if norm not in seen:
                seen.add(norm)
                unique_dirs.append(d)

        return unique_dirs

    def resolve_target_save_path(
        self,
        save_dirs: List[Path],
        rom_path: str,
        remote_filename: str = "",
        remote_ext: str = "",
        platform_slug: str = "",
    ) -> Path:
        """Determine default target path to place/download the Wii save file.

        Args:
            save_dirs: Candidate save directories.
            rom_path: Path to ROM file.
            remote_filename: Optional filename from RomM server.
            remote_ext: Optional remote extension.
            platform_slug: Platform identifier slug.

        Returns:
            Resolved destination Path object.
        """
        meta = self.extract_rom_metadata(rom_path)
        tid_low = meta.get("title_id_low")
        if not tid_low:
            game_code = meta.get("game_code", "")
            if game_code:
                tid_low = game_code.encode("latin1").hex().lower()
            else:
                stem = Path(rom_path).stem if rom_path else "unknown"
                tid_low = sanitize_filename(stem)

        # Locate first available title root
        primary_dir = save_dirs[0] if save_dirs else Path(".")
        for d in save_dirs:
            if d.exists() and "00010000" in str(d).lower():
                primary_dir = d
                break

        if "00010000" in str(primary_dir).lower():
            target_data_dir = primary_dir / tid_low.lower() / "data"
        else:
            target_data_dir = (
                primary_dir
                / "dolphin-emu"
                / "User"
                / "Wii"
                / "title"
                / "00010000"
                / tid_low.lower()
                / "data"
            )

        if remote_filename and remote_filename.lower().endswith(".zip"):
            return target_data_dir.parent / remote_filename
        elif remote_filename and remote_filename.lower().endswith(".bin"):
            return target_data_dir / remote_filename
        elif remote_filename:
            return target_data_dir / remote_filename

        return target_data_dir / f"{tid_low.lower()}.zip"

    def find_existing_save(
        self,
        save_dirs: List[Path],
        rom_path: str,
        remote_filename: str = "",
        remote_ext: str = "",
        platform_slug: str = "",
    ) -> Optional[Path]:
        """Search candidate directories for existing Wii save data.

        Args:
            save_dirs: Candidate save directories.
            rom_path: Path to ROM.
            remote_filename: Optional remote filename.
            remote_ext: Optional remote extension.
            platform_slug: Platform identifier slug.

        Returns:
            Path to existing save file or consolidated save zip if found, or None.
        """
        meta = self.extract_rom_metadata(rom_path)
        tid_low = meta.get("title_id_low", "")
        game_code = meta.get("game_code", "")

        tids_to_try: List[str] = []
        if tid_low:
            tids_to_try.extend([tid_low.lower(), tid_low.upper()])
        if game_code:
            code_hex = game_code.encode("latin1").hex().lower()
            if code_hex not in tids_to_try:
                tids_to_try.extend([code_hex.lower(), code_hex.upper()])
            tids_to_try.extend([game_code.lower(), game_code.upper()])

        for s_dir in save_dirs:
            if not s_dir.exists():
                continue

            # 1. Inspect title directory / title roots (e.g. title/00010000/<tid>/data)
            title_root = s_dir if "00010000" in str(s_dir).lower() else None
            if not title_root:
                for sub in [
                    s_dir / "dolphin-emu" / "User" / "Wii" / "title" / "00010000",
                    s_dir / "User" / "Wii" / "title" / "00010000",
                    s_dir / "Wii" / "title" / "00010000",
                    s_dir / "title" / "00010000",
                ]:
                    if sub.exists():
                        title_root = sub
                        break

            if title_root and title_root.exists() and title_root.is_dir():
                check_tids = tids_to_try
                if not check_tids:
                    try:
                        check_tids = [d.name for d in title_root.iterdir() if d.is_dir()]
                    except Exception:
                        check_tids = []

                for tid in check_tids:
                    data_dir = title_root / tid / "data"
                    if data_dir.exists() and data_dir.is_dir():
                        try:
                            save_files = [
                                f
                                for f in data_dir.iterdir()
                                if f.is_file()
                                and not f.name.startswith(".")
                                and not f.name.endswith(".tmp")
                                and not f.name.endswith(".zip")
                            ]
                            # If remote explicitly asked for data.bin and it exists, return data.bin
                            if (
                                remote_filename
                                and remote_filename.lower() == "data.bin"
                                and (data_dir / "data.bin").is_file()
                            ):
                                return data_dir / "data.bin"

                            # If directory has files, consolidate into zip
                            if len(save_files) >= 1:
                                zip_target = data_dir.parent / f"{tid}.zip"
                                return consolidate_wii_save_directory(data_dir, zip_target)
                        except Exception as e:
                            logger.debug("Error inspecting Wii save files in %s: %s", data_dir, e)

                    # Check for pre-existing packaged zip in title root
                    zip_cand = title_root / tid / f"{tid}.zip"
                    if zip_cand.is_file():
                        return zip_cand

            # 2. Direct file search in candidate directory (e.g. next to ROM or legacy exports)
            stem = Path(rom_path).stem if rom_path else ""
            for name in [
                f"{stem}.zip",
                f"{stem}.bin",
                f"{stem}.sav",
                f"{stem}.dat",
                "data.bin",
                "banner.bin",
            ]:
                cand = s_dir / name
                if cand.is_file():
                    return cand

        return None
