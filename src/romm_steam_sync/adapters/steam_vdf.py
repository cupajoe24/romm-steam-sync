"""Steam Binary shortcuts.vdf parser, serializer, and AppID generator."""

import logging
import struct
from typing import Any, Dict, List, Tuple
import zlib

logger = logging.getLogger(__name__)


def generate_app_id(exe: str, app_name: str) -> Tuple[int, int, str]:
    """Generate 32-bit int, 64-bit int, and string representation of Steam Non-Steam AppID.

    Formula:
        crc = CRC32(clean_exe + app_name)
        appid_32 = crc | 0x80000000
        appid_64 = (appid_32 << 32) | 0x02000000

    Args:
        exe: Executable launch target string.
        app_name: Display name of the non-Steam shortcut.

    Returns:
        Tuple of (appid_32_signed, appid_64_unsigned, str_representation).
    """
    clean_exe = exe.strip('"')
    key = f"{clean_exe}{app_name}".encode("utf-8")
    crc = zlib.crc32(key)
    appid_32_unsigned = crc | 0x80000000

    # Convert to signed 32-bit int for VDF int field if needed
    if appid_32_unsigned >= 0x80000000:
        appid_32_signed = appid_32_unsigned - 0x100000000
    else:
        appid_32_signed = appid_32_unsigned

    appid_64 = (appid_32_unsigned << 32) | 0x02000000
    str_id = str(appid_32_unsigned)

    return appid_32_signed, appid_64, str_id


class BinaryVdfParser:
    """Parses and serializes Steam binary shortcuts.vdf files."""

    TYPE_OBJECT = 0
    TYPE_STRING = 1
    TYPE_INT32 = 2
    TYPE_END = 8

    @classmethod
    def parse(cls, data: bytes) -> Dict[str, Any]:
        """Parse binary VDF buffer into nested Python dictionaries.

        Args:
            data: Raw binary VDF bytes.

        Returns:
            Parsed dictionary tree representing VDF structure.
        """

        def read_cstring(b: bytes, off: int) -> Tuple[str, int]:
            """Read null-terminated UTF-8 C-string from byte buffer."""
            end = b.find(b"\x00", off)
            if end == -1:
                return "", len(b)
            return b[off:end].decode("utf-8", errors="replace"), end + 1

        def parse_object(b: bytes, off: int) -> Tuple[Dict[str, Any], int]:
            """Recursively parse binary object key-value pairs."""
            obj: Dict[str, Any] = {}
            while off < len(b):
                type_byte = b[off]
                off += 1
                if type_byte == cls.TYPE_END:
                    break

                key, off = read_cstring(b, off)
                if type_byte == cls.TYPE_OBJECT:
                    child_obj, off = parse_object(b, off)
                    obj[key] = child_obj
                elif type_byte == cls.TYPE_STRING:
                    val, off = read_cstring(b, off)
                    obj[key] = val
                elif type_byte == cls.TYPE_INT32:
                    val = struct.unpack("<i", b[off : off + 4])[0]
                    off += 4
                    obj[key] = val
                else:
                    # Unknown byte, attempt skip
                    break
            return obj, off

        result, _ = parse_object(data, 0)
        return result

    @classmethod
    def serialize(cls, data: Dict[str, Any]) -> bytes:
        """Serialize nested dictionary back into Steam binary VDF buffer.

        Args:
            data: Nested dictionary structure to serialize.

        Returns:
            Serialized bytes buffer.
        """
        out = bytearray()

        def write_cstring(s: str) -> None:
            """Write null-terminated UTF-8 string to output buffer."""
            out.extend(s.encode("utf-8"))
            out.append(0)

        def serialize_object(obj: Dict[str, Any]) -> None:
            """Recursively write object key-value pairs in binary VDF format."""
            for k, v in obj.items():
                if isinstance(v, dict):
                    out.append(cls.TYPE_OBJECT)
                    write_cstring(str(k))
                    serialize_object(v)
                elif isinstance(v, str):
                    out.append(cls.TYPE_STRING)
                    write_cstring(str(k))
                    write_cstring(v)
                elif isinstance(v, int):
                    out.append(cls.TYPE_INT32)
                    write_cstring(str(k))
                    out.extend(struct.pack("<i", v))
            out.append(cls.TYPE_END)

        serialize_object(data)
        return bytes(out)


class SteamVdfManager:
    """High-level manager for reading, mutating, and writing shortcuts.vdf.

    Attributes:
        vdf_path: Filesystem path to target shortcuts.vdf file.
    """

    def __init__(self, vdf_path: str) -> None:
        """Initialize SteamVdfManager with path to shortcuts.vdf.

        Args:
            vdf_path: Path string to shortcuts.vdf.
        """
        self.vdf_path = vdf_path

    def load_shortcuts(self) -> List[Dict[str, Any]]:
        """Load shortcuts list from shortcuts.vdf file.

        Returns:
            List of shortcut dictionaries.
        """
        try:
            with open(self.vdf_path, "rb") as f:
                content = f.read()
            parsed = BinaryVdfParser.parse(content)
            shortcuts_dict = parsed.get("shortcuts", {})
            shortcuts_list = []
            for idx in sorted(
                shortcuts_dict.keys(),
                key=lambda x: int(x) if x.isdigit() else x,
            ):
                shortcuts_list.append(shortcuts_dict[idx])
            logger.info(
                "Loaded %d shortcuts from %s", len(shortcuts_list), self.vdf_path
            )
            return shortcuts_list
        except FileNotFoundError:
            logger.info(
                "shortcuts.vdf file not found at %s (will be created)",
                self.vdf_path,
            )
            return []
        except Exception as e:
            logger.error(
                "Failed to parse shortcuts.vdf at %s: %s", self.vdf_path, e
            )
            return []

    def save_shortcuts(self, shortcuts: List[Dict[str, Any]]) -> None:
        """Serialize and save shortcuts list to shortcuts.vdf file.

        Args:
            shortcuts: List of shortcut dictionaries to write.

        Raises:
            Exception: If file writing or serialization fails.
        """
        try:
            shortcuts_dict = {str(i): s for i, s in enumerate(shortcuts)}
            vdf_root = {"shortcuts": shortcuts_dict}
            binary_data = BinaryVdfParser.serialize(vdf_root)
            with open(self.vdf_path, "wb") as f:
                f.write(binary_data)
            logger.info(
                "Successfully saved %d shortcuts to %s",
                len(shortcuts),
                self.vdf_path,
            )
        except Exception as e:
            logger.error(
                "Failed to save shortcuts.vdf at %s: %s", self.vdf_path, e
            )
            raise
