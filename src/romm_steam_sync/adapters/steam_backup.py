"""Steam VDF Backup and Rollback Manager."""

from datetime import datetime
import logging
from pathlib import Path
import shutil
from typing import Dict, List, Optional, Set

from romm_steam_sync.adapters.steam_localconfig import SteamLocalConfigManager
from romm_steam_sync.adapters.steam_vdf import SteamVdfManager, generate_app_id
from romm_steam_sync.config import get_default_config_dir

logger = logging.getLogger(__name__)


class SteamBackupManager:
    """Manages creation, retention limits, and restoration of Steam shortcut backups.

    Attributes:
        backup_dir: Root directory where timestamped backups are stored.
    """

    MAX_BACKUPS = 5

    def __init__(self, backup_root_dir: Optional[Path] = None) -> None:
        """Initialize SteamBackupManager with target directory.

        Args:
            backup_root_dir: Optional custom directory to store backups.
        """
        if backup_root_dir is None:
            self.backup_dir = get_default_config_dir() / "backups"
        else:
            self.backup_dir = backup_root_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, steam_config_dir: str) -> str:
        """Create a timestamped backup folder for Steam config files and enforce retention.

        Args:
            steam_config_dir: Path to user's Steam config directory.

        Returns:
            Folder name ID of the newly created backup.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_folder_name = f"backup_{timestamp}"
        target_dir = self.backup_dir / backup_folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        config_path = Path(steam_config_dir)
        source_vdf = config_path / "shortcuts.vdf"
        source_localconfig = config_path / "localconfig.vdf"
        source_cloudstorage = config_path / "cloudstorage"

        files_backed_up = 0
        if source_vdf.exists():
            shutil.copy2(source_vdf, target_dir / "shortcuts.vdf")
            files_backed_up += 1

        if source_localconfig.exists():
            shutil.copy2(source_localconfig, target_dir / "localconfig.vdf")
            files_backed_up += 1

        if source_cloudstorage.exists() and source_cloudstorage.is_dir():
            target_cs = target_dir / "cloudstorage"
            if target_cs.exists():
                shutil.rmtree(target_cs)
            shutil.copytree(source_cloudstorage, target_cs)
            files_backed_up += 1

        if files_backed_up == 0:
            (target_dir / ".initial_empty_state").write_text(
                "Initial state before sync", encoding="utf-8"
            )

        logger.info(
            "Created Steam config backup: %s (%d files backed up)",
            backup_folder_name,
            files_backed_up,
        )

        # Prune old backups exceeding retention limit
        self.prune_old_backups()

        return backup_folder_name

    def prune_old_backups(self) -> List[str]:
        """Delete older backup directories if count exceeds MAX_BACKUPS limit (5).

        Returns:
            List of pruned backup folder names.
        """
        backups = self._get_sorted_backup_dirs()
        deleted: List[str] = []
        while len(backups) > self.MAX_BACKUPS:
            oldest = backups.pop(0)
            try:
                shutil.rmtree(oldest)
                deleted.append(oldest.name)
                logger.info("Pruned old Steam backup: %s", oldest.name)
            except Exception as e:
                logger.warning("Failed to remove old backup %s: %s", oldest, e)
        return deleted

    def list_backups(self) -> List[Dict[str, str]]:
        """List available backups ordered from newest to oldest.

        Returns:
            List of dictionaries containing backup metadata ('id', 'created_at', 'path').
        """
        result: List[Dict[str, str]] = []
        for b_dir in reversed(self._get_sorted_backup_dirs()):
            created_at_str = self._format_backup_timestamp(b_dir.name)
            if not created_at_str:
                created_at_str = datetime.fromtimestamp(
                    b_dir.stat().st_mtime
                ).strftime("%Y-%m-%d %H:%M:%S")

            result.append({
                "id": b_dir.name,
                "created_at": created_at_str,
                "path": str(b_dir),
            })
        return result

    def restore_backup(self, backup_id: str, steam_config_dir: str) -> bool:
        """Restore shortcuts.vdf, localconfig.vdf, and cloudstorage from a backup folder.

        Args:
            backup_id: Identifier folder name of backup.
            steam_config_dir: Destination Steam config path.

        Returns:
            True if restoration succeeded, False otherwise.
        """
        backup_folder = self.backup_dir / backup_id
        if not backup_folder.exists():
            logger.error("Backup folder %s does not exist", backup_folder)
            return False

        target_config = Path(steam_config_dir)
        target_config.mkdir(parents=True, exist_ok=True)

        backup_vdf = backup_folder / "shortcuts.vdf"
        backup_local = backup_folder / "localconfig.vdf"
        backup_cs = backup_folder / "cloudstorage"

        try:
            # 1. Restore shortcuts.vdf
            if backup_vdf.exists():
                shutil.copy2(backup_vdf, target_config / "shortcuts.vdf")
            elif (target_config / "shortcuts.vdf").exists():
                (target_config / "shortcuts.vdf").unlink()

            # 2. Restore localconfig.vdf if present in backup folder
            if backup_local.exists():
                shutil.copy2(backup_local, target_config / "localconfig.vdf")
            else:
                self._resync_localconfig_from_vdf(target_config)

            # 3. Restore cloudstorage directory if present in backup folder
            if backup_cs.exists() and backup_cs.is_dir():
                target_cs = target_config / "cloudstorage"
                if target_cs.exists():
                    shutil.rmtree(target_cs)
                shutil.copytree(backup_cs, target_cs)
            else:
                self._resync_localconfig_from_vdf(target_config)

            logger.info(
                "Successfully restored config files from backup %s", backup_id
            )
            return True
        except Exception as e:
            logger.error("Failed to restore backup %s: %s", backup_id, e)
            return False

    def _resync_localconfig_from_vdf(self, target_config: Path) -> None:
        """Re-sync localconfig.vdf CloudCollections based on current shortcuts.vdf.

        Args:
            target_config: Path to Steam config folder.
        """
        vdf_path = target_config / "shortcuts.vdf"
        if not vdf_path.exists():
            return

        try:
            vdf_mgr = SteamVdfManager(str(vdf_path))
            shortcuts = vdf_mgr.load_shortcuts()

            platform_app_ids: Dict[str, Set[int]] = {}
            master_app_ids: Set[int] = set()

            for s in shortcuts:
                exe = s.get("Exe", "")
                app_name = s.get("AppName", "")
                tags = s.get("tags", {})
                _a32, a64, _ = generate_app_id(exe, app_name)

                master_app_ids.add(a64)
                p_name = tags.get("1") or "RomM"
                if p_name not in platform_app_ids:
                    platform_app_ids[p_name] = set()
                platform_app_ids[p_name].add(a64)

            localconfig_mgr = SteamLocalConfigManager(str(target_config))
            localconfig_mgr.update_collections(platform_app_ids, master_app_ids)
        except Exception as e:
            logger.warning("Failed to resync localconfig during rollback: %s", e)

    def _get_sorted_backup_dirs(self) -> List[Path]:
        """Find and return all backup directories sorted chronologically.

        Returns:
            List of Path objects sorted from oldest to newest.
        """
        dirs = [
            p
            for p in self.backup_dir.iterdir()
            if p.is_dir() and p.name.startswith("backup_")
        ]
        dirs.sort(key=lambda p: p.name)
        return dirs

    @staticmethod
    def _format_backup_timestamp(folder_name: str) -> str:
        """Parse folder name timestamp (backup_YYYYMMDD_HHMMSS_ffffff) to readable string.

        Args:
            folder_name: Name of backup directory.

        Returns:
            Human readable date string or empty string if parse failed.
        """
        try:
            parts = folder_name.split("_")
            if len(parts) >= 3:
                date_str, time_str = parts[1], parts[2]
                dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.debug(
                "Failed parsing backup timestamp for folder '%s': %s",
                folder_name,
                e,
            )
        return ""
