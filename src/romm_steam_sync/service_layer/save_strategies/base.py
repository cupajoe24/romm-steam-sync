"""Abstract base class for platform and core-specific save synchronization strategies."""

from abc import ABC, abstractmethod
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import zipfile

from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.domain.save_sync_state import RomSaveSyncState
from romm_steam_sync.service_layer.db_session import DatabaseSession

logger = logging.getLogger(__name__)


def calculate_save_hash(file_path: str) -> str:
    """Calculate RomM-compatible MD5 content hash for a save file.

    For single binary files: MD5 of raw bytes.
    For Zip archives: MD5 of sorted entry hashes (name:md5\\n).

    Args:
        file_path: Path to the save file.

    Returns:
        Hexadecimal MD5 string or empty string if missing.
    """
    path = Path(file_path)
    if not path.exists():
        return ""

    if zipfile.is_zipfile(path):
        try:
            entries: List[Tuple[str, str]] = []
            with zipfile.ZipFile(path, "r") as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    data = zf.read(member.filename)
                    entry_md5 = hashlib.md5(data).hexdigest()
                    entries.append((member.filename, entry_md5))

            entries.sort(key=lambda x: x[0])
            joined_lines = "".join(f"{name}:{h}\n" for name, h in entries)
            return hashlib.md5(joined_lines.encode("utf-8")).hexdigest()
        except Exception as e:
            logger.warning(
                "Failed zip-aware hashing for %s, falling back to raw file MD5: %s",
                file_path,
                e,
            )

    hasher = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class BaseSaveStrategy(ABC):
    """Abstract base class for platform and core-specific save synchronization strategies.

    Attributes:
        name: Unique identifier name of the save strategy.
    """

    name: str = "base"

    def _fetch_remote_save(
        self,
        client: RomMApiClient,
        rom_id: int,
        slot: str = "autosave",
    ) -> Optional[Dict[str, Any]]:
        """Fetch remote save metadata dictionary from RomM API.

        Args:
            client: RomMApiClient instance.
            rom_id: RomM identifier of the game.
            slot: Save slot identifier.

        Returns:
            Matched remote save metadata dict, or None if not found.
        """
        try:
            remote_saves = client.get_saves(rom_id, slot=slot)
            return remote_saves[0] if remote_saves else None
        except Exception as e:
            logger.warning(
                "Could not fetch remote saves from RomM for rom_id %s: %s",
                rom_id,
                e,
            )
            return None

    def _load_baseline(
        self, rom_id: int, file_name: str
    ) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        """Load latest save baseline hashes and size from local SQLite database.

        Args:
            rom_id: RomM identifier of the game.
            file_name: Name of the save file.

        Returns:
            Tuple of (last_sync_hash, last_sync_server_hash, last_sync_local_size).
        """
        try:
            with DatabaseSession() as db:
                state = db.save_sync_states.get(rom_id)
                if state:
                    fstate = state.get_file_state(file_name)
                    if fstate:
                        return (
                            fstate.last_sync_hash,
                            fstate.last_sync_server_hash,
                            fstate.last_sync_local_size,
                        )
        except Exception as e:
            logger.debug(
                "Database lookup for save sync baseline skipped: %s", e
            )
        return None, None, None

    def _record_baseline(
        self,
        rom_id: int,
        target_save_path: Path,
        slot: str = "autosave",
        remote_save: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record latest save baseline to local SQLite database.

        Args:
            rom_id: RomM identifier of the game.
            target_save_path: Path to target save file.
            slot: Save slot identifier.
            remote_save: Optional remote save metadata dictionary.
        """
        try:
            with DatabaseSession() as db:
                st = db.save_sync_states.get(rom_id) or RomSaveSyncState(
                    rom_id=rom_id, active_slot=slot
                )
                nhash = (
                    calculate_save_hash(str(target_save_path))
                    if target_save_path.exists()
                    else None
                )
                nsize = (
                    target_save_path.stat().st_size
                    if target_save_path.exists()
                    else None
                )
                nmtime = (
                    target_save_path.stat().st_mtime
                    if target_save_path.exists()
                    else None
                )
                shash = (
                    remote_save.get("content_hash") if remote_save else None
                )
                tid = remote_save.get("id") if remote_save else None
                st.adopt_baseline(
                    file_name=target_save_path.name,
                    last_sync_hash=nhash,
                    last_sync_server_hash=shash,
                    last_sync_local_size=nsize,
                    last_sync_local_mtime=nmtime,
                    tracked_save_id=tid,
                )
                db.save_sync_states.add(st)
                db.commit()
        except Exception as e:
            logger.warning("Failed saving Gavel sync baseline record: %s", e)

    def _match_remote_save(
        self,
        client: RomMApiClient,
        rom_id: int,
        save_p: Path,
        slot: str = "autosave",
    ) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        """Match remote save entry by file name, extension, or single-entry fallback.

        Args:
            client: RomMApiClient instance.
            rom_id: RomM identifier of the game.
            save_p: Path to local save file.
            slot: Target save slot.

        Returns:
            Tuple of (save_id_or_none, remote_save_dict_or_none).
        """
        try:
            remote_saves = client.get_saves(rom_id, slot=slot)
            if not remote_saves:
                return None, None
            for rs in remote_saves:
                r_name = rs.get("name") or rs.get("file_name") or ""
                r_ext = rs.get("file_extension") or ""
                if r_name.lower() == save_p.name.lower() or (
                    r_ext and save_p.suffix.lower() == f".{r_ext.lower()}"
                ):
                    return rs.get("id"), rs
            if len(remote_saves) == 1:
                return remote_saves[0].get("id"), remote_saves[0]
        except Exception as e:
            logger.warning(
                "Failed matching remote save from RomM for rom_id %s: %s",
                rom_id,
                e,
            )
        return None, None

    @abstractmethod
    def find_local_save_file(
        self,
        rom_path: str,
        platform_slug: str = "",
        configured_retroarch_path: str = "",
        remote_ext: str = "",
        core_name: str = "",
        **kwargs: Any,
    ) -> Tuple[Optional[Path], Path]:
        """Locate local save file for game/platform.

        Args:
            rom_path: Path to the ROM file.
            platform_slug: Platform slug identifier.
            configured_retroarch_path: Configured RetroArch binary/install path.
            remote_ext: Optional extension of the remote save file.
            core_name: Specific libretro core name.
            **kwargs: Extra strategy-specific keyword parameters.

        Returns:
            Tuple of (existing_save_path_or_none, fallback_target_path).
        """

    @abstractmethod
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
            rom_path: Path to the ROM file.
            platform_slug: Platform identifier.
            client: RomMApiClient instance.
            configured_retroarch_path: Optional RetroArch executable path.
            slot: Target save slot.
            core_name: Optional core identifier.
            **kwargs: Extra strategy arguments.

        Returns:
            Tuple of (action_decision, reason_message, remote_save_dict, local_save_path).
        """

    @abstractmethod
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
            save_path: Path to local save file.
            client: RomMApiClient instance.
            slot: Target save slot.
            platform_slug: Optional platform slug.
            configured_retroarch_path: Optional RetroArch path.
            rom_path: Optional ROM path.
            core_name: Optional core name.
            **kwargs: Extra strategy arguments.

        Returns:
            Tuple of (success_boolean, status_message).
        """
