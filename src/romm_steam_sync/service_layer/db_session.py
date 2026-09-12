"""SQLite Database Session and Repository Infrastructure."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional
from typing_extensions import Self

from romm_steam_sync.config import get_default_config_dir
from romm_steam_sync.domain import (
    FileSyncState,
    KvConfig,
    PlaySession,
    Rom,
    RomInstall,
    RomPlaytime,
    RomSaveSyncState,
    SyncRun,
)

logger = logging.getLogger(__name__)


def get_default_db_path() -> Path:
    """Get the default filesystem path to the application SQLite database.

    Returns:
        Path pointing to 'romm_steam_sync.db'.
    """
    return get_default_config_dir() / "romm_steam_sync.db"


class RomRepository:
    """Repository handling CRUD operations for Rom aggregate entities."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize RomRepository with active SQLite connection.

        Args:
            conn: Active sqlite3.Connection.
        """
        self.conn = conn

    def get(self, rom_id: int) -> Optional[Rom]:
        """Fetch a Rom by its RomM ID.

        Args:
            rom_id: Unique RomM identifier.

        Returns:
            Rom instance if found, or None.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT rom_id, platform_slug, name, shortcut_app_id,
                      sibling_group_key, summary, cover_url, fs_name,
                      sgdb_id, igdb_id
               FROM roms WHERE rom_id = ?""",
            (rom_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Rom(
            rom_id=row[0],
            platform_slug=row[1],
            name=row[2],
            shortcut_app_id=row[3],
            sibling_group_key=row[4],
            summary=row[5],
            cover_url=row[6],
            fs_name=row[7],
            sgdb_id=row[8],
            igdb_id=row[9],
        )

    def add(self, rom: Rom) -> None:
        """Insert or update a Rom in the database.

        Args:
            rom: Rom aggregate entity to persist.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO roms (
                   rom_id, platform_slug, name, shortcut_app_id,
                   sibling_group_key, summary, cover_url, fs_name,
                   sgdb_id, igdb_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(rom_id) DO UPDATE SET
                   platform_slug=excluded.platform_slug,
                   name=excluded.name,
                   shortcut_app_id=excluded.shortcut_app_id,
                   sibling_group_key=excluded.sibling_group_key,
                   summary=excluded.summary,
                   cover_url=excluded.cover_url,
                   fs_name=excluded.fs_name,
                   sgdb_id=excluded.sgdb_id,
                   igdb_id=excluded.igdb_id""",
            (
                rom.rom_id,
                rom.platform_slug,
                rom.name,
                rom.shortcut_app_id,
                rom.sibling_group_key,
                rom.summary,
                rom.cover_url,
                rom.fs_name,
                rom.sgdb_id,
                rom.igdb_id,
            ),
        )

    def list_all(self) -> List[Rom]:
        """List all persisted Rom entities.

        Returns:
            List of all Rom entities.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT rom_id, platform_slug, name, shortcut_app_id,
                      sibling_group_key, summary, cover_url, fs_name,
                      sgdb_id, igdb_id
               FROM roms"""
        )
        rows = cursor.fetchall()
        return [
            Rom(
                rom_id=r[0],
                platform_slug=r[1],
                name=r[2],
                shortcut_app_id=r[3],
                sibling_group_key=r[4],
                summary=r[5],
                cover_url=r[6],
                fs_name=r[7],
                sgdb_id=r[8],
                igdb_id=r[9],
            )
            for r in rows
        ]

    def get_by_sibling_group(self, sibling_group_key: str) -> List[Rom]:
        """Fetch all ROMs belonging to a sibling group.

        Args:
            sibling_group_key: Sibling group key string.

        Returns:
            List of sibling Rom entities.
        """
        if not sibling_group_key:
            return []
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT rom_id, platform_slug, name, shortcut_app_id,
                      sibling_group_key, summary, cover_url, fs_name,
                      sgdb_id, igdb_id
               FROM roms WHERE sibling_group_key = ?""",
            (sibling_group_key,),
        )
        rows = cursor.fetchall()
        return [
            Rom(
                rom_id=r[0],
                platform_slug=r[1],
                name=r[2],
                shortcut_app_id=r[3],
                sibling_group_key=r[4],
                summary=r[5],
                cover_url=r[6],
                fs_name=r[7],
                sgdb_id=r[8],
                igdb_id=r[9],
            )
            for r in rows
        ]

    def get_siblings(self, rom_id: int) -> List[Rom]:
        """Fetch all sibling ROMs associated with a given ROM ID (including itself).

        Args:
            rom_id: ROM ID to find siblings for.

        Returns:
            List of sibling Rom entities.
        """
        rom = self.get(rom_id)
        if not rom:
            return []
        if not rom.sibling_group_key:
            return [rom]
        return self.get_by_sibling_group(rom.sibling_group_key)

    def get_bound_rom(self, sibling_group_key: str) -> Optional[Rom]:
        """Fetch the active bound ROM for a sibling group.

        Args:
            sibling_group_key: Target sibling group key.

        Returns:
            Bound Rom instance if bound, or None.
        """
        if not sibling_group_key:
            return None
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT rom_id, platform_slug, name, shortcut_app_id,
                      sibling_group_key, summary, cover_url, fs_name,
                      sgdb_id, igdb_id
               FROM roms
               WHERE sibling_group_key = ? AND shortcut_app_id IS NOT NULL""",
            (sibling_group_key,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return Rom(
            rom_id=row[0],
            platform_slug=row[1],
            name=row[2],
            shortcut_app_id=row[3],
            sibling_group_key=row[4],
            summary=row[5],
            cover_url=row[6],
            fs_name=row[7],
            sgdb_id=row[8],
            igdb_id=row[9],
        )

    def unbind_all_in_group(self, sibling_group_key: str) -> None:
        """Clear shortcut_app_id for all ROMs in a sibling group.

        Args:
            sibling_group_key: Target sibling group key.
        """
        if not sibling_group_key:
            return
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE roms SET shortcut_app_id = NULL WHERE sibling_group_key = ?",
            (sibling_group_key,),
        )

    def delete(self, rom_id: int) -> None:
        """Delete a single Rom by ID.

        Args:
            rom_id: ROM ID to delete.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM roms WHERE rom_id = ?", (rom_id,))

    def delete_by_platform(
        self, platform_slug: str, aliases: Optional[List[str]] = None
    ) -> int:
        """Delete all ROMs belonging to a specific platform.

        Args:
            platform_slug: Target platform slug.
            aliases: Optional list of alias slugs to include.

        Returns:
            Number of deleted ROM records.
        """
        cursor = self.conn.cursor()
        targets = set([platform_slug.lower()])
        if aliases:
            targets.update(a.lower() for a in aliases)

        placeholders = ",".join("?" for _ in targets)
        cursor.execute(
            f"DELETE FROM roms WHERE LOWER(platform_slug) IN ({placeholders})",
            list(targets),
        )
        return cursor.rowcount

    def delete_all(self) -> int:
        """Delete all Rom entities from database.

        Returns:
            Number of deleted records.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM roms")
        return cursor.rowcount

    def get_platform_counts(self) -> Dict[str, int]:
        """Get counts of synced ROMs grouped by platform slug.

        Returns:
            Mapping of platform slug to count of ROM records.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT platform_slug, COUNT(*) FROM roms GROUP BY platform_slug"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}


class RomInstallRepository:
    """Repository handling CRUD operations for RomInstall aggregates."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize RomInstallRepository.

        Args:
            conn: Active sqlite3.Connection.
        """
        self.conn = conn

    def get(self, rom_id: int) -> Optional[RomInstall]:
        """Fetch local install record for a ROM.

        Args:
            rom_id: RomM identifier.

        Returns:
            RomInstall instance if present, or None.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT rom_id, file_path, rom_dir, launchable, installed_at
               FROM rom_installs WHERE rom_id = ?""",
            (rom_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        installed_at_dt = None
        if row[4]:
            try:
                installed_at_dt = datetime.fromisoformat(row[4])
            except Exception as e:
                logger.warning(
                    "Failed parsing installed_at ISO timestamp '%s' for rom_id %s: %s",
                    row[4],
                    row[0],
                    e,
                )
                installed_at_dt = None

        return RomInstall(
            rom_id=row[0],
            file_path=row[1],
            rom_dir=row[2],
            launchable=bool(row[3]),
            installed_at=installed_at_dt,
        )

    def add(self, install: RomInstall) -> None:
        """Insert or update a RomInstall record.

        Args:
            install: RomInstall entity to persist.
        """
        cursor = self.conn.cursor()
        installed_at_str = (
            install.installed_at.isoformat() if install.installed_at else None
        )
        cursor.execute(
            """INSERT INTO rom_installs (
                   rom_id, file_path, rom_dir, launchable, installed_at
               ) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(rom_id) DO UPDATE SET
                   file_path=excluded.file_path,
                   rom_dir=excluded.rom_dir,
                   launchable=excluded.launchable,
                   installed_at=excluded.installed_at""",
            (
                install.rom_id,
                install.file_path,
                install.rom_dir,
                1 if install.launchable else 0,
                installed_at_str,
            ),
        )

    def delete(self, rom_id: int) -> None:
        """Delete local install record for a ROM.

        Args:
            rom_id: Target ROM identifier.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM rom_installs WHERE rom_id = ?", (rom_id,))

    def list_all(self) -> List[RomInstall]:
        """List all RomInstall entities.

        Returns:
            List of all RomInstall entities.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT rom_id, file_path, rom_dir, launchable, installed_at
               FROM rom_installs"""
        )
        rows = cursor.fetchall()
        installs = []
        for row in rows:
            installed_at_dt = None
            if row[4]:
                try:
                    installed_at_dt = datetime.fromisoformat(row[4])
                except Exception as e:
                    logger.warning(
                        "Failed parsing installed_at ISO timestamp '%s' for rom_id %s: %s",
                        row[4],
                        row[0],
                        e,
                    )
                    installed_at_dt = None
            installs.append(
                RomInstall(
                    rom_id=row[0],
                    file_path=row[1],
                    rom_dir=row[2],
                    launchable=bool(row[3]),
                    installed_at=installed_at_dt,
                )
            )
        return installs

    def delete_all(self) -> int:
        """Delete all RomInstall records.

        Returns:
            Number of deleted records.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM rom_installs")
        return cursor.rowcount


class SyncRunRepository:
    """Repository handling CRUD operations for SyncRun entities."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize SyncRunRepository.

        Args:
            conn: Active sqlite3.Connection.
        """
        self.conn = conn

    def add(self, run: SyncRun) -> None:
        """Insert or update a SyncRun record.

        Args:
            run: SyncRun entity to persist.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO sync_runs (
                   run_id, started_at, status, completed_at,
                   synced_rom_count, error_message
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(run_id) DO UPDATE SET
                   status=excluded.status,
                   completed_at=excluded.completed_at,
                   synced_rom_count=excluded.synced_rom_count,
                   error_message=excluded.error_message""",
            (
                run.run_id,
                run.started_at.isoformat() if run.started_at else None,
                run.status,
                run.completed_at.isoformat() if run.completed_at else None,
                run.synced_rom_count,
                run.error_message,
            ),
        )


class KvConfigRepository:
    """Repository handling key-value configuration storage in SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize KvConfigRepository.

        Args:
            conn: Active sqlite3.Connection.
        """
        self.conn = conn

    def get(self, key: str) -> Optional[KvConfig]:
        """Fetch a configuration pair by key name.

        Args:
            key: Target configuration key name.

        Returns:
            KvConfig instance if found, or None.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT key, value, updated_at FROM kv_config WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return KvConfig(key=row[0], value=row[1], updated_at=row[2])

    def set(self, key: str, value: str) -> None:
        """Insert or update a configuration key-value pair.

        Args:
            key: Configuration key name.
            value: Configuration value string.
        """
        cursor = self.conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """INSERT INTO kv_config (key, value, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                   value=excluded.value,
                   updated_at=excluded.updated_at""",
            (key, value, now),
        )


class RomSaveSyncStateRepository:
    """Repository handling CRUD operations for RomSaveSyncState aggregates."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize RomSaveSyncStateRepository.

        Args:
            conn: Active sqlite3.Connection.
        """
        self.conn = conn

    def get(self, rom_id: int) -> Optional[RomSaveSyncState]:
        """Fetch save sync state for a ROM.

        Args:
            rom_id: Target ROM ID.

        Returns:
            RomSaveSyncState instance if found, or None.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT rom_id, slot_confirmed, active_slot, file_states_json
               FROM rom_save_sync_states WHERE rom_id = ?""",
            (rom_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        file_states: Dict[str, FileSyncState] = {}
        if row[3]:
            try:
                data = json.loads(row[3])
                for fname, fdict in data.items():
                    file_states[fname] = FileSyncState(
                        file_name=fname,
                        last_sync_hash=fdict.get("last_sync_hash"),
                        last_sync_server_hash=fdict.get(
                            "last_sync_server_hash"
                        ),
                        last_sync_local_size=fdict.get("last_sync_local_size"),
                        last_sync_local_mtime=fdict.get(
                            "last_sync_local_mtime"
                        ),
                        tracked_save_id=fdict.get("tracked_save_id"),
                        last_synced_at=fdict.get("last_synced_at"),
                    )
            except Exception as e:
                logger.warning(
                    "Failed to deserialize file_states_json for rom_id %s: %s",
                    rom_id,
                    e,
                )

        return RomSaveSyncState(
            rom_id=row[0],
            slot_confirmed=bool(row[1]),
            active_slot=row[2] or "autosave",
            file_states=file_states,
        )

    def add(self, state: RomSaveSyncState) -> None:
        """Insert or update a RomSaveSyncState record.

        Args:
            state: RomSaveSyncState entity to persist.
        """
        cursor = self.conn.cursor()
        serialized_files: Dict[str, dict] = {}
        for fname, fstate in state.file_states.items():
            serialized_files[fname] = {
                "file_name": fstate.file_name,
                "last_sync_hash": fstate.last_sync_hash,
                "last_sync_server_hash": fstate.last_sync_server_hash,
                "last_sync_local_size": fstate.last_sync_local_size,
                "last_sync_local_mtime": fstate.last_sync_local_mtime,
                "tracked_save_id": fstate.tracked_save_id,
                "last_synced_at": fstate.last_synced_at,
            }

        file_states_json = json.dumps(serialized_files)
        cursor.execute(
            """INSERT INTO rom_save_sync_states (
                   rom_id, slot_confirmed, active_slot, file_states_json
               ) VALUES (?, ?, ?, ?)
               ON CONFLICT(rom_id) DO UPDATE SET
                   slot_confirmed=excluded.slot_confirmed,
                   active_slot=excluded.active_slot,
                   file_states_json=excluded.file_states_json""",
            (
                state.rom_id,
                1 if state.slot_confirmed else 0,
                state.active_slot,
                file_states_json,
            ),
        )


class DatabaseSession:
    """Context manager controlling SQLite database transaction boundaries.

    Attributes:
        db_path: Path to target SQLite database file.
        conn: Active sqlite3.Connection.
        roms: RomRepository instance.
        installs: RomInstallRepository instance.
        sync_runs: SyncRunRepository instance.
        kv_config: KvConfigRepository instance.
        save_sync_states: RomSaveSyncStateRepository instance.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize DatabaseSession.

        Args:
            db_path: Optional custom path to SQLite database.
        """
        self.db_path = db_path or get_default_db_path()
        self.conn: Optional[sqlite3.Connection] = None
        self.roms: RomRepository
        self.installs: RomInstallRepository
        self.sync_runs: SyncRunRepository
        self.kv_config: KvConfigRepository
        self.save_sync_states: RomSaveSyncStateRepository

    def __enter__(self) -> Self:
        """Enter database context, creating tables and instantiating repositories.

        Returns:
            Active DatabaseSession instance.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._init_tables()
        self.roms = RomRepository(self.conn)
        self.installs = RomInstallRepository(self.conn)
        self.sync_runs = SyncRunRepository(self.conn)
        self.kv_config = KvConfigRepository(self.conn)
        self.save_sync_states = RomSaveSyncStateRepository(self.conn)
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any],
    ) -> None:
        """Exit database context, performing rollback on error and closing connection.

        Args:
            exc_type: Exception type if raised in context block.
            exc_val: Exception instance.
            exc_tb: Exception traceback.
        """
        if self.conn:
            if exc_type is not None:
                self.rollback()
            self.conn.close()

    def commit(self) -> None:
        """Commit active database transaction."""
        if self.conn:
            self.conn.commit()

    def rollback(self) -> None:
        """Rollback active database transaction."""
        if self.conn:
            self.conn.rollback()

    def _init_tables(self) -> None:
        """Initialize table schemas and migrations if missing."""
        if not self.conn:
            return
        cursor = self.conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS roms (
                rom_id INTEGER PRIMARY KEY,
                platform_slug TEXT NOT NULL,
                name TEXT NOT NULL,
                shortcut_app_id INTEGER,
                sibling_group_key TEXT,
                summary TEXT,
                cover_url TEXT,
                fs_name TEXT,
                sgdb_id INTEGER,
                igdb_id INTEGER
            );

            CREATE TABLE IF NOT EXISTS rom_installs (
                rom_id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL,
                rom_dir TEXT,
                launchable INTEGER NOT NULL DEFAULT 1,
                installed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS rom_save_sync_states (
                rom_id INTEGER PRIMARY KEY,
                slot_confirmed INTEGER NOT NULL DEFAULT 0,
                active_slot TEXT NOT NULL DEFAULT 'slot1',
                file_states_json TEXT
            );

            CREATE TABLE IF NOT EXISTS rom_playtime (
                rom_id INTEGER PRIMARY KEY,
                total_seconds INTEGER NOT NULL DEFAULT 0,
                last_played_at TEXT,
                pending_sessions_json TEXT
            );

            CREATE TABLE IF NOT EXISTS sync_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                status TEXT NOT NULL,
                completed_at TEXT,
                synced_rom_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS kv_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT
            );
            """
        )
        # Migrations for pre-existing databases lacking sgdb_id / igdb_id columns
        cursor.execute("PRAGMA table_info(roms);")
        columns = [col[1] for col in cursor.fetchall()]
        if "sgdb_id" not in columns:
            cursor.execute("ALTER TABLE roms ADD COLUMN sgdb_id INTEGER;")
        if "igdb_id" not in columns:
            cursor.execute("ALTER TABLE roms ADD COLUMN igdb_id INTEGER;")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_roms_sibling_group ON roms(sibling_group_key);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_roms_shortcut_app_id ON roms(shortcut_app_id);"
        )
        self.conn.commit()
