"""Citra RetroArch core and standalone Citra 3DS save handler implementation."""

import logging
import os
from pathlib import Path
import re
import struct
from typing import Any, Dict, List, Optional
import zipfile

from romm_steam_sync.adapters.retroarch_launcher import RetroArchLauncher
from romm_steam_sync.service_layer.save_strategies.handlers.base import (
    BaseMemoryCardHandler,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

# 3DS NCSD container magic at offset 0x100
_NCSD_MAGIC = b"NCSD"
# 3DS NCCH partition magic at offset 0x100
_NCCH_MAGIC = b"NCCH"

# Default dummy Citra ID0 and ID1 directory strings (32 zeros)
DEFAULT_CITRA_ID0 = "00000000000000000000000000000000"
DEFAULT_CITRA_ID1 = "00000000000000000000000000000000"

# Region code mapping from 3DS product code character to region name
# (Product codes follow CTR-P-xxxx or CTR-N-xxxx where the 4th character is the region code)
REGION_CHAR_MAP: Dict[str, str] = {
    "E": "USA",
    "U": "USA",
    "P": "EUR",
    "V": "EUR",
    "X": "EUR",
    "Y": "EUR",
    "D": "EUR",
    "F": "EUR",
    "I": "EUR",
    "S": "EUR",
    "H": "EUR",
    "J": "JAP",
    "K": "KOR",
    "C": "CHN",
    "T": "TWN",
    "A": "ALL",
}

# Regex patterns to detect region from ROM filename tags
REGION_TAG_PATTERNS: List[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(USA|North America|US|NTSC-U)\b", re.IGNORECASE), "USA"),
    (
        re.compile(
            r"\b(Europe|EUR|EU|PAL|Germany|France|Spain|Italy|UK|En,Fr,De,Es,It)\b",
            re.IGNORECASE,
        ),
        "EUR",
    ),
    (re.compile(r"\b(Japan|JAP|JPN|JP|NTSC-J)\b", re.IGNORECASE), "JAP"),
    (re.compile(r"\b(Korea|KOR|KO|K)\b", re.IGNORECASE), "KOR"),
    (re.compile(r"\b(China|CHN|ZH)\b", re.IGNORECASE), "CHN"),
    (re.compile(r"\b(Taiwan|TWN)\b", re.IGNORECASE), "TWN"),
    (re.compile(r"\b(World|Global|ALL)\b", re.IGNORECASE), "ALL"),
]

# Regex pattern to detect Title ID from filename tags like [0004000000054000] or [00054000]
TITLE_ID_TAG_PATTERN = re.compile(
    r"\[([0-9a-fA-F]{8}|00040000[0-9a-fA-F]{8})\]", re.IGNORECASE
)


def _detect_region_from_text(text: str) -> str:
    """Detect region name from filename or product code string.

    Args:
        text: Text string to inspect for region tags.

    Returns:
        Region string (USA, EUR, JAP, KOR, CHN, TWN, or ALL).
    """
    for pattern, reg in REGION_TAG_PATTERNS:
        if pattern.search(text):
            return reg
    return "USA"


def _parse_ncch_header(data: bytes) -> Optional[Dict[str, Any]]:
    """Parse NCCH container header bytes (requires at least 0x160 bytes).

    Args:
        data: Byte buffer containing NCCH header starting with NCCH magic at 0x100 or 0x00.

    Returns:
        Extracted metadata dictionary if valid NCCH header found, or None.
    """
    if len(data) < 0x160:
        return None

    offset = 0
    if data[0x100:0x104] == _NCCH_MAGIC:
        offset = 0x100
    elif data[0:4] == _NCCH_MAGIC:
        offset = 0
    else:
        return None

    if len(data) < offset + 0x60:
        return None

    maker_code = (
        data[offset + 0x08 : offset + 0x0A]
        .decode("latin1", errors="ignore")
        .strip()
    )
    raw_title_id = struct.unpack_from("<Q", data, offset + 0x18)[0]
    full_title_id = f"{raw_title_id:016X}"
    title_id_low = f"{raw_title_id & 0xFFFFFFFF:08X}"

    product_code = ""
    if len(data) >= offset + 0x60:
        raw_prod = (
            data[offset + 0x50 : offset + 0x60]
            .split(b"\x00")[0]
            .decode("latin1", errors="ignore")
            .strip()
        )
        product_code = raw_prod

    region = "USA"
    if len(product_code) >= 10:
        code_char = product_code[9].upper()
        if code_char in REGION_CHAR_MAP:
            region = REGION_CHAR_MAP[code_char]

    return {
        "title_id": full_title_id,
        "title_id_low": title_id_low,
        "maker_code": maker_code,
        "product_code": product_code,
        "region": region,
        "valid_header": True,
    }


def _parse_3ds_data_slice(data: bytes) -> Optional[Dict[str, Any]]:
    """Parse a slice of 3DS header data (from raw file or zip entry).

    Args:
        data: Byte buffer containing at least 0x200 bytes.

    Returns:
        Extracted metadata dictionary if valid header found, or None.
    """
    if len(data) < 0x200:
        return None

    # 1. NCSD Cartridge / Card Image (.3ds / .cci)
    if len(data) >= 0x104 and data[0x100:0x104] == _NCSD_MAGIC:
        media_id_raw = struct.unpack_from("<Q", data, 0x108)[0]
        full_title_id = f"{media_id_raw:016X}"
        title_id_low = f"{media_id_raw & 0xFFFFFFFF:08X}"

        meta: Dict[str, Any] = {
            "title_id": full_title_id,
            "title_id_low": title_id_low,
            "maker_code": "",
            "product_code": "",
            "region": "USA",
            "valid_header": True,
        }

        # Inspect partition 0 in partition table at offset 0x120
        if len(data) >= 0x128:
            part0_offset_media_units = struct.unpack_from(
                "<I", data, 0x120
            )[0]
            part0_offset = part0_offset_media_units * 0x200
            if part0_offset > 0 and len(data) >= part0_offset + 0x160:
                ncch_meta = _parse_ncch_header(data[part0_offset:])
                if ncch_meta:
                    meta.update(ncch_meta)

        return meta

    # 2. Raw NCCH Executable (.cxi / .app)
    if len(data) >= 0x104 and (data[0x100:0x104] == _NCCH_MAGIC or data[0:4] == _NCCH_MAGIC):
        return _parse_ncch_header(data)

    return None


def read_3ds_rom_header(file_path: Path) -> Optional[Dict[str, Any]]:
    """Extract 3DS ROM header metadata across container formats (.3ds, .cci, .cxi, .app, .zip).

    Args:
        file_path: Filesystem path to 3DS ROM file or compressed archive.

    Returns:
        Extracted metadata dictionary if valid header found, or None.
    """
    try:
        if not file_path.is_file() or file_path.stat().st_size < 0x200:
            return None

        # Handle .zip archives containing 3DS ROMs
        if zipfile.is_zipfile(file_path):
            try:
                with zipfile.ZipFile(file_path, "r") as zf:
                    for member in zf.infolist():
                        if member.is_dir():
                            continue
                        m_name = member.filename.lower()
                        if m_name.endswith((".3ds", ".cci", ".cxi", ".app")):
                            with zf.open(member) as zf_entry:
                                data = zf_entry.read(65536)
                                meta = _parse_3ds_data_slice(data)
                                if meta and meta.get("valid_header"):
                                    return meta
            except Exception as e:
                logger.debug("Error inspecting zip archive for 3DS header in %s: %s", file_path, e)

        # Handle raw uncompressed 3DS ROM files
        with open(file_path, "rb") as f:
            data = f.read(65536)

        return _parse_3ds_data_slice(data)

    except Exception as e:
        logger.debug(
            "Error reading 3DS ROM header from %s: %s", file_path, e
        )

    return None


def consolidate_3ds_save_directory(data_dir: Path, target_zip: Path) -> Path:
    """Bundle 3DS save container directory files into a deterministic zip archive.

    Args:
        data_dir: Directory containing 3DS save files (e.g. data/00000001).
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
            "Consolidated %d 3DS save files from %s into %s",
            len(save_files),
            data_dir,
            target_zip,
        )

    return target_zip


def unpack_3ds_save_archive(zip_path: Path, dest_data_dir: Path) -> None:
    """Unpack 3DS save archive contents safely into the destination data folder.

    Args:
        zip_path: Path to the downloaded .zip save archive.
        dest_data_dir: Target data directory (e.g. data/00000001).
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
    logger.info("Unpacked 3DS save archive %s into %s", zip_path.name, dest_data_dir)


class Citra3DSHandler(BaseMemoryCardHandler):
    """Save handler for Nintendo 3DS games using Citra libretro core and standalone Citra."""

    def extract_rom_metadata(self, rom_path: str) -> Dict[str, Any]:
        """Extract Title ID, Product Code, Maker Code, Region, and Title from 3DS ROM.

        Args:
            rom_path: Path to the 3DS ROM file.

        Returns:
            Dictionary containing extracted metadata fields.
        """
        p = Path(rom_path) if rom_path else None
        stem = p.stem if p else ""

        extracted = read_3ds_rom_header(p) if p and p.is_file() else None
        if extracted and extracted.get("valid_header"):
            extracted["title"] = stem
            if extracted.get("region") == "USA":
                detected_reg = _detect_region_from_text(stem)
                if detected_reg != "USA":
                    extracted["region"] = detected_reg
            return extracted

        # Fallback if binary header is encrypted or unavailable
        title_id_match = TITLE_ID_TAG_PATTERN.search(stem)
        tid = title_id_match.group(1).upper() if title_id_match else ""
        if len(tid) == 16:
            full_tid = tid
            tid_low = tid[8:]
        elif len(tid) == 8:
            full_tid = f"00040000{tid}"
            tid_low = tid
        else:
            full_tid = ""
            tid_low = ""

        return {
            "title_id": full_tid,
            "title_id_low": tid_low,
            "maker_code": "",
            "product_code": "",
            "region": _detect_region_from_text(stem),
            "title": stem,
            "valid_header": bool(tid_low),
        }

    def get_save_directories(
        self,
        configured_retroarch_path: str = "",
        rom_path: str = "",
        platform_slug: str = "",
    ) -> List[Path]:
        """Resolve candidate save directories where Citra expects SDMC save data.

        Args:
            configured_retroarch_path: Configured path to RetroArch binary.
            rom_path: Path to ROM.
            platform_slug: Platform identifier slug.

        Returns:
            List of candidate save directories.
        """
        candidate_dirs: List[Path] = []
        base_roots_to_scan: List[Path] = []

        # 1. Configured RetroArch binary directory
        ra_exe = RetroArchLauncher.resolve_retroarch_binary(
            configured_retroarch_path
        )
        if ra_exe:
            ra_parent = Path(ra_exe).parent
            saves_p = ra_parent / "saves"
            base_roots_to_scan.append(saves_p)
            candidate_dirs.extend([
                saves_p / "Citra" / "Citra" / "sdmc" / "Nintendo 3DS",
                saves_p / "Citra" / "sdmc" / "Nintendo 3DS",
                saves_p / "citra" / "citra" / "sdmc" / "Nintendo 3DS",
                saves_p / "citra" / "sdmc" / "Nintendo 3DS",
                saves_p / "3ds" / "Citra" / "sdmc" / "Nintendo 3DS",
                saves_p / "3ds" / "sdmc" / "Nintendo 3DS",
                ra_parent / "system" / "Citra" / "sdmc" / "Nintendo 3DS",
                saves_p,
            ])

        # 2. System and user home directory standard paths
        home = Path.home()
        if os.name == "nt":
            appdata = (
                Path(os.environ.get("APPDATA", ""))
                if os.environ.get("APPDATA")
                else home / "AppData" / "Roaming"
            )
            localappdata = (
                Path(os.environ.get("LOCALAPPDATA", ""))
                if os.environ.get("LOCALAPPDATA")
                else home / "AppData" / "Local"
            )

            ra_appdata_saves = appdata / "RetroArch" / "saves"
            base_roots_to_scan.append(ra_appdata_saves)

            candidate_dirs.extend([
                ra_appdata_saves / "Citra" / "Citra" / "sdmc" / "Nintendo 3DS",
                ra_appdata_saves / "Citra" / "sdmc" / "Nintendo 3DS",
                ra_appdata_saves / "citra" / "citra" / "sdmc" / "Nintendo 3DS",
                ra_appdata_saves / "citra" / "sdmc" / "Nintendo 3DS",
                Path(r"C:\RetroArch-Win64\saves\Citra\Citra\sdmc\Nintendo 3DS"),
                Path(r"C:\RetroArch-Win64\saves\Citra\sdmc\Nintendo 3DS"),
                Path(r"C:\Program Files\RetroArch-Win64\saves\Citra\sdmc\Nintendo 3DS"),
                Path(r"C:\Program Files (x86)\RetroArch-Win64\saves\Citra\sdmc\Nintendo 3DS"),
                # Standalone Citra Windows paths
                appdata / "Citra" / "sdmc" / "Nintendo 3DS",
                localappdata / "Citra" / "sdmc" / "Nintendo 3DS",
                ra_appdata_saves,
            ])
        else:
            ra_config_saves = home / ".config" / "retroarch" / "saves"
            ra_flatpak_saves = (
                home
                / ".var"
                / "app"
                / "org.libretro.RetroArch"
                / "config"
                / "retroarch"
                / "saves"
            )
            base_roots_to_scan.extend([ra_config_saves, ra_flatpak_saves])

            candidate_dirs.extend([
                # Linux Native RetroArch
                ra_config_saves / "Citra" / "Citra" / "sdmc" / "Nintendo 3DS",
                ra_config_saves / "Citra" / "sdmc" / "Nintendo 3DS",
                ra_config_saves / "citra" / "citra" / "sdmc" / "Nintendo 3DS",
                ra_config_saves / "citra" / "sdmc" / "Nintendo 3DS",
                # Linux Flatpak RetroArch
                ra_flatpak_saves / "Citra" / "Citra" / "sdmc" / "Nintendo 3DS",
                ra_flatpak_saves / "Citra" / "sdmc" / "Nintendo 3DS",
                # RetroDECK
                home
                / ".var"
                / "app"
                / "net.retrodeck.retrodeck"
                / "config"
                / "retrodeck"
                / "saves"
                / "Citra"
                / "sdmc"
                / "Nintendo 3DS",
                # Standalone Citra Linux paths
                home / ".local" / "share" / "citra-emu" / "sdmc" / "Nintendo 3DS",
                home
                / ".var"
                / "app"
                / "org.citra_emu.citra"
                / "data"
                / "citra-emu"
                / "sdmc"
                / "Nintendo 3DS",
                # macOS Paths
                home
                / "Library"
                / "Application Support"
                / "RetroArch"
                / "saves"
                / "Citra"
                / "Citra"
                / "sdmc"
                / "Nintendo 3DS",
                home
                / "Library"
                / "Application Support"
                / "RetroArch"
                / "saves"
                / "Citra"
                / "sdmc"
                / "Nintendo 3DS",
                home
                / "Library"
                / "Application Support"
                / "Citra"
                / "sdmc"
                / "Nintendo 3DS",
                ra_config_saves,
            ])

        # 3. Dynamic scan of base save directories for existing 'Nintendo 3DS' roots
        for b_root in base_roots_to_scan:
            if b_root.exists() and b_root.is_dir():
                try:
                    for found_n3ds in b_root.rglob("Nintendo 3DS"):
                        if found_n3ds.is_dir():
                            candidate_dirs.insert(0, found_n3ds)
                except Exception as e:
                    logger.debug("Error scanning base directory %s for Nintendo 3DS: %s", b_root, e)

        # 4. Content Directory next to ROM
        if rom_path:
            p_rom = Path(rom_path)
            candidate_dirs.append(
                p_rom.parent / "Citra" / "sdmc" / "Nintendo 3DS"
            )
            candidate_dirs.append(p_rom.parent)

        # Filter duplicates while maintaining order
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
        """Determine standard target path to place/download the 3DS save file.

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
            stem = Path(rom_path).stem if rom_path else "unknown"
            tid_low = sanitize_filename(stem)

        # Primary save directory root
        primary_dir = save_dirs[0] if save_dirs else Path(".")

        if "nintendo 3ds" in str(primary_dir).lower():
            target_folder = (
                primary_dir
                / DEFAULT_CITRA_ID0
                / DEFAULT_CITRA_ID1
                / "title"
                / "00040000"
                / tid_low.lower()
                / "data"
                / "00000001"
            )
        else:
            target_folder = (
                primary_dir
                / "Citra"
                / "Citra"
                / "sdmc"
                / "Nintendo 3DS"
                / DEFAULT_CITRA_ID0
                / DEFAULT_CITRA_ID1
                / "title"
                / "00040000"
                / tid_low.lower()
                / "data"
                / "00000001"
            )

        if remote_filename and remote_filename.lower().endswith(".zip"):
            return target_folder.parent / remote_filename
        elif remote_filename:
            return target_folder / remote_filename
        return target_folder / "00000001.zip"

    def find_existing_save(
        self,
        save_dirs: List[Path],
        rom_path: str,
        remote_filename: str = "",
        remote_ext: str = "",
        platform_slug: str = "",
    ) -> Optional[Path]:
        """Search candidate directories for existing Citra 3DS save file.

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

        tids_to_try: List[str] = []
        if tid_low:
            tids_to_try.extend([tid_low.lower(), tid_low.upper()])

        for s_dir in save_dirs:
            if not s_dir.exists():
                continue

            # Resolve Nintendo 3DS root
            n3ds_root = s_dir if "nintendo 3ds" in str(s_dir).lower() else None
            if not n3ds_root:
                for sub in [
                    s_dir / "Citra" / "Citra" / "sdmc" / "Nintendo 3DS",
                    s_dir / "Citra" / "sdmc" / "Nintendo 3DS",
                    s_dir / "citra" / "citra" / "sdmc" / "Nintendo 3DS",
                    s_dir / "citra" / "sdmc" / "Nintendo 3DS",
                    s_dir / "Nintendo 3DS",
                ]:
                    if sub.exists():
                        n3ds_root = sub
                        break

            if n3ds_root and n3ds_root.exists() and n3ds_root.is_dir():
                # 1. Search default dummy IDs and custom console folders
                candidate_title_roots: List[Path] = [
                    n3ds_root / DEFAULT_CITRA_ID0 / DEFAULT_CITRA_ID1 / "title" / "00040000"
                ]

                try:
                    for id0_dir in n3ds_root.iterdir():
                        if not id0_dir.is_dir():
                            continue
                        for id1_dir in id0_dir.iterdir():
                            if not id1_dir.is_dir():
                                continue
                            t_root = id1_dir / "title" / "00040000"
                            if t_root.exists() and t_root.is_dir() and t_root not in candidate_title_roots:
                                candidate_title_roots.append(t_root)
                except Exception as e:
                    logger.debug("Error iterating console ID directories in %s: %s", n3ds_root, e)

                for t_root in candidate_title_roots:
                    if not t_root.exists() or not t_root.is_dir():
                        continue

                    # If no title ID was extracted from ROM, check if any subfolders exist in t_root
                    check_tids = tids_to_try
                    if not check_tids:
                        try:
                            check_tids = [d.name for d in t_root.iterdir() if d.is_dir()]
                        except Exception:
                            check_tids = []

                    for tid in check_tids:
                        data_dir = t_root / tid / "data" / "00000001"
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
                                if len(save_files) == 1 and save_files[0].name.lower() in ["main", "main.sav"] and not (remote_filename and remote_filename.lower().endswith(".zip")):
                                    return save_files[0]
                                elif len(save_files) >= 1:
                                    zip_target = data_dir.parent / "00000001.zip"
                                    return consolidate_3ds_save_directory(data_dir, zip_target)
                            except Exception as e:
                                logger.debug("Error reading save files from %s: %s", data_dir, e)

                        # Check for pre-existing packaged zip in data folder
                        zip_cand = t_root / tid / "data" / "00000001.zip"
                        if zip_cand.is_file():
                            return zip_cand

            # Case B: Direct file search in candidate directory (e.g. next to ROM)
            stem = Path(rom_path).stem if rom_path else ""
            for name in [f"{stem}.sav", f"{stem}.srm", f"{stem}.main", f"{stem}.zip", "main", "main.zip"]:
                cand = s_dir / name
                if cand.is_file():
                    return cand

        return None
