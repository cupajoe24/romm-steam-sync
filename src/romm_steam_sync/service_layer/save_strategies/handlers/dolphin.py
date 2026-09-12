"""Base Dolphin core and emulator save handler implementation."""

import logging
import os
from pathlib import Path
import re
import struct
from typing import Any, Dict, List, Optional
import zlib

from romm_steam_sync.adapters.retroarch_launcher import RetroArchLauncher
from romm_steam_sync.service_layer.save_strategies.handlers.base import (
    BaseMemoryCardHandler,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

# GameCube disc header magic at offset 0x1C
_GC_MAGIC = b"\xc2\x33\x9f\x3d"

# Wii disc header magic at offset 0x18
_WII_MAGIC = b"\x5d\x1c\x9e\xa3"

# Supported Dolphin region directories
SUPPORTED_REGIONS: List[str] = ["USA", "EUR", "JAP", "KOR"]

# Region character mapping to Dolphin region folder names
REGION_CHAR_MAP: Dict[str, str] = {
    "E": "USA",
    "U": "USA",
    "P": "EUR",
    "D": "EUR",
    "F": "EUR",
    "I": "EUR",
    "S": "EUR",
    "X": "EUR",
    "Y": "EUR",
    "A": "EUR",
    "V": "EUR",
    "J": "JAP",
    "K": "KOR",
    "W": "KOR",
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
]


def parse_disc_header_slice(
    slice_bytes: bytes, is_wii: bool = False
) -> Optional[Dict[str, Any]]:
    """Parse a raw 0x60-byte disc boot header slice for GameCube or Wii.

    Args:
        slice_bytes: Byte buffer containing at least 0x20 header bytes.
        is_wii: Whether to extract Wii-specific Title ID fields.

    Returns:
        Dictionary of extracted header fields, or None.
    """
    if len(slice_bytes) < 0x20:
        return None

    raw_game_code = slice_bytes[0:4].decode("latin1", errors="ignore")
    raw_maker_code = slice_bytes[4:6].decode("latin1", errors="ignore")
    disc_number = slice_bytes[6] if len(slice_bytes) > 6 else 0
    disc_version = slice_bytes[7] if len(slice_bytes) > 7 else 0

    raw_title = ""
    if len(slice_bytes) >= 0x60:
        raw_title = (
            slice_bytes[0x20:0x60]
            .split(b"\x00")[0]
            .decode("latin1", errors="ignore")
            .strip()
        )

    if len(raw_game_code) == 4 and raw_game_code.isalnum():
        region = "USA"
        region_char = raw_game_code[3].upper()
        if region_char in REGION_CHAR_MAP:
            region = REGION_CHAR_MAP[region_char]

        meta: Dict[str, Any] = {
            "game_code": raw_game_code,
            "maker_code": raw_maker_code,
            "disc_number": disc_number,
            "disc_version": disc_version,
            "title": raw_title,
            "valid_header": True,
            "region": region,
        }

        if is_wii:
            game_code_hex = raw_game_code.encode("latin1").hex().lower()
            meta["title_id_low"] = game_code_hex
            meta["title_id"] = f"00010000{game_code_hex.upper()}"

        return meta

    return None


def read_disc_container_header(
    file_path: Path,
    magic: bytes,
    magic_offset: int,
    is_wii: bool = False,
) -> Optional[Dict[str, Any]]:
    """Extract disc header across container variations (ISO, GCM, RVZ, WIA, WBFS, CISO, GCZ, TGC).

    Args:
        file_path: Filesystem path to ROM file.
        magic: Expected magic bytes (_GC_MAGIC or _WII_MAGIC).
        magic_offset: Offset of magic within 0x60 disc header (0x1C for GC, 0x18 for Wii).
        is_wii: Whether to extract Wii Title ID metadata.

    Returns:
        Extracted metadata dictionary if valid header found, or None.
    """
    try:
        if not file_path.is_file() or file_path.stat().st_size < 0x20:
            return None

        with open(file_path, "rb") as f:
            data = f.read(65536)

        if len(data) < 0x20:
            return None

        magic_len = len(magic)

        # 1. Standard raw ISO / GCM (magic at magic_offset)
        if (
            len(data) >= magic_offset + magic_len
            and data[magic_offset : magic_offset + magic_len] == magic
        ):
            return parse_disc_header_slice(data[0:0x60], is_wii=is_wii)

        # 2. RVZ / WIA Container (magic RVZ\x01 or WIA\x01, header at offset 0x48)
        if data.startswith(b"RVZ\x01") or data.startswith(b"WIA\x01"):
            target_offset = 0x48 + magic_offset
            if (
                len(data) >= target_offset + magic_len
                and data[target_offset : target_offset + magic_len] == magic
            ):
                return parse_disc_header_slice(
                    data[0x48 : 0x48 + 0x60], is_wii=is_wii
                )

        # 3. WBFS Container (magic WBFS, disc 0 header at 0x100 or 0x200)
        if data.startswith(b"WBFS"):
            for disc_offset in [0x100, 0x200]:
                target_offset = disc_offset + magic_offset
                if (
                    len(data) >= target_offset + magic_len
                    and data[target_offset : target_offset + magic_len] == magic
                ):
                    return parse_disc_header_slice(
                        data[disc_offset : disc_offset + 0x60], is_wii=is_wii
                    )

        # 4. CISO / CSO Compact ISO (magic CISO, block 0 at offset 0x8000)
        if data.startswith(b"CISO"):
            target_offset = 0x8000 + magic_offset
            if (
                len(data) >= target_offset + magic_len
                and data[target_offset : target_offset + magic_len] == magic
            ):
                return parse_disc_header_slice(
                    data[0x8000 : 0x8000 + 0x60], is_wii=is_wii
                )

        # 5. GCZ Dolphin Compressed (magic \xb1\x0b\xc0\x01, decompress block 0)
        if data.startswith(b"\xb1\x0b\xc0\x01") and len(data) >= 24:
            try:
                num_blocks = struct.unpack_from("<I", data, 20)[0]
                block0_offset = 0x18 + num_blocks * 8
                if len(data) > block0_offset:
                    comp_block = data[block0_offset : block0_offset + 32768]
                    decomp = zlib.decompress(comp_block)
                    if (
                        len(decomp) >= magic_offset + magic_len
                        and decomp[magic_offset : magic_offset + magic_len] == magic
                    ):
                        return parse_disc_header_slice(
                            decomp[0:0x60], is_wii=is_wii
                        )
            except Exception as e:
                logger.debug(
                    "Failed decompressing GCZ block 0 for %s: %s", file_path, e
                )

        # 6. Generic scan for magic within first 64KB (handles TGC, custom offsets, padded formats)
        magic_idx = data.find(magic)
        if magic_idx >= magic_offset:
            start_slice = magic_idx - magic_offset
            return parse_disc_header_slice(
                data[start_slice : start_slice + 0x60], is_wii=is_wii
            )

        # 7. Fallback check for unadorned 4-char game code
        raw_code = data[0:4].decode("latin1", errors="ignore")
        if len(raw_code) == 4 and raw_code.isalnum():
            if (not is_wii and raw_code.startswith("G")) or (
                is_wii and raw_code[0] in "RSWD"
            ):
                return parse_disc_header_slice(data[0:0x60], is_wii=is_wii)

    except Exception as e:
        logger.debug(
            "Error reading disc container header from %s: %s", file_path, e
        )

    return None


class BaseDolphinHandler(BaseMemoryCardHandler):
    """Shared base handler for Dolphin emulator and libretro core save management."""

    def get_base_save_directories(
        self,
        configured_retroarch_path: str = "",
    ) -> List[Path]:
        """Resolve base RetroArch saves directories across platforms.

        Args:
            configured_retroarch_path: Configured RetroArch binary path.

        Returns:
            List of base RetroArch save directory paths.
        """
        base_save_dirs: List[Path] = []

        # 1. Configured RetroArch binary directory saves
        ra_exe = RetroArchLauncher.resolve_retroarch_binary(
            configured_retroarch_path
        )
        if ra_exe:
            exe_parent = Path(ra_exe).parent
            base_save_dirs.append(exe_parent / "saves")

        # 2. Standard user home / OS RetroArch directories
        home = Path.home()
        if os.name == "nt":
            appdata = (
                Path(os.environ.get("APPDATA", ""))
                if os.environ.get("APPDATA")
                else home / "AppData" / "Roaming"
            )
            base_save_dirs.extend([
                appdata / "RetroArch" / "saves",
                home / "AppData" / "Roaming" / "RetroArch" / "saves",
                Path(r"C:\RetroArch-Win64\saves"),
                Path(r"C:\Program Files\RetroArch-Win64\saves"),
                Path(r"C:\Program Files (x86)\RetroArch-Win64\saves"),
            ])
        else:
            base_save_dirs.extend([
                home / ".config" / "retroarch" / "saves",
                home
                / ".var"
                / "app"
                / "org.libretro.RetroArch"
                / "config"
                / "retroarch"
                / "saves",
                home
                / "Library"
                / "Application Support"
                / "RetroArch"
                / "saves",
            ])

        # Deduplicate while preserving order
        seen = set()
        unique_dirs: List[Path] = []
        for d in base_save_dirs:
            norm = str(d).lower()
            if norm not in seen:
                seen.add(norm)
                unique_dirs.append(d)

        return unique_dirs

    def detect_region_from_tags(self, text: str) -> Optional[str]:
        """Match filename tags against known regional patterns.

        Args:
            text: Filename or string to inspect.

        Returns:
            Matched region name (e.g. 'USA', 'EUR', 'JAP', 'KOR'), or None.
        """
        for pattern, reg in REGION_TAG_PATTERNS:
            if pattern.search(text):
                return reg
        return None

    def clean_string_for_matching(self, s: str) -> str:
        """Remove punctuation and lowercase a string for relaxed comparison.

        Args:
            s: Input string.

        Returns:
            Alphanumeric lowercase string.
        """
        return re.sub(r"[^a-zA-Z0-9]", "", s).lower()


DolphinHandler = BaseDolphinHandler

# Re-exports for backwards compatibility
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin_gamecube import (
    DolphinGameCubeHandler,
    read_gc_container_header,
    read_gci_header,
)
from romm_steam_sync.service_layer.save_strategies.handlers.dolphin_wii import (
    DolphinWiiHandler,
    consolidate_wii_save_directory,
    read_wii_disc_header,
    unpack_wii_save_archive,
)

__all__ = [
    "BaseDolphinHandler",
    "DolphinGameCubeHandler",
    "DolphinHandler",
    "DolphinWiiHandler",
    "REGION_CHAR_MAP",
    "REGION_TAG_PATTERNS",
    "SUPPORTED_REGIONS",
    "_GC_MAGIC",
    "_WII_MAGIC",
    "consolidate_wii_save_directory",
    "parse_disc_header_slice",
    "read_disc_container_header",
    "read_gc_container_header",
    "read_gci_header",
    "read_wii_disc_header",
    "unpack_wii_save_archive",
]
