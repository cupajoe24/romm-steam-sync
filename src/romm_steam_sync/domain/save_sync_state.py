"""RomSaveSyncState aggregate root and FileSyncState value object."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass(frozen=True)
class FileSyncState:
    """Per-file sync baseline metadata recorded at a successful sync boundary.

    Attributes:
        file_name: Base filename of the save file (e.g. 'game.srm').
        last_sync_hash: Local MD5/SHA hash computed at last sync.
        last_sync_server_hash: Remote server hash at last sync.
        last_sync_local_size: Local file size in bytes at last sync.
        last_sync_local_mtime: Local file mtime epoch timestamp at last sync.
        tracked_save_id: RomM remote save record identifier.
        last_synced_at: ISO 8601 UTC timestamp string of sync completion.
    """

    file_name: str
    last_sync_hash: Optional[str] = None
    last_sync_server_hash: Optional[str] = None
    last_sync_local_size: Optional[int] = None
    last_sync_local_mtime: Optional[float] = None
    tracked_save_id: Optional[int] = None
    last_synced_at: Optional[str] = None


@dataclass
class RomSaveSyncState:
    """Per-ROM save synchronization state aggregate root.

    Attributes:
        rom_id: RomM identifier of the game.
        slot_confirmed: Whether the user has explicitly confirmed the save slot.
        active_slot: Currently selected save slot (e.g. 'autosave', 'slot1').
        file_states: Mapping of save filenames to their respective FileSyncState.
    """

    rom_id: int
    slot_confirmed: bool = False
    active_slot: str = "autosave"
    file_states: Dict[str, FileSyncState] = field(default_factory=dict)

    def get_file_state(self, file_name: str) -> Optional[FileSyncState]:
        """Retrieve the recorded sync state for a specific save file.

        Args:
            file_name: Name of the save file to look up.

        Returns:
            FileSyncState if recorded, or None if never synced.
        """
        return self.file_states.get(file_name)

    def update_file_state(self, state: FileSyncState) -> None:
        """Update or insert the sync state for a save file.

        Args:
            state: FileSyncState instance to persist.
        """
        self.file_states[state.file_name] = state

    def adopt_baseline(
        self,
        file_name: str,
        last_sync_hash: str,
        last_sync_server_hash: Optional[str] = None,
        last_sync_local_size: Optional[int] = None,
        last_sync_local_mtime: Optional[float] = None,
        tracked_save_id: Optional[int] = None,
    ) -> None:
        """Record baseline metadata at a successful sync boundary.

        Args:
            file_name: Base name of the save file.
            last_sync_hash: Local file hash at sync point.
            last_sync_server_hash: Remote server hash at sync point.
            last_sync_local_size: Local file size in bytes.
            last_sync_local_mtime: Local file mtime timestamp.
            tracked_save_id: Remote RomM save record ID.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        state = FileSyncState(
            file_name=file_name,
            last_sync_hash=last_sync_hash,
            last_sync_server_hash=last_sync_server_hash,
            last_sync_local_size=last_sync_local_size,
            last_sync_local_mtime=last_sync_local_mtime,
            tracked_save_id=tracked_save_id,
            last_synced_at=now_iso,
        )
        self.file_states[file_name] = state
