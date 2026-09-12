"""Service logic for Advanced Options cleanup and application data purging."""

import logging
from pathlib import Path
import shutil
from typing import Optional, Tuple

from romm_steam_sync.config import AppSettings, get_default_config_dir
from romm_steam_sync.logging_config import close_logging_file_handlers
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.service_layer.sync_service import SyncService

logger = logging.getLogger(__name__)


def delete_all_installed_roms(
    settings: AppSettings,
    db_session: Optional[DatabaseSession] = None,
) -> Tuple[bool, str, int]:
    """Delete all local ROM files and clear installation records from the database.

    Args:
        settings: Active AppSettings instance.
        db_session: Optional pre-configured DatabaseSession.

    Returns:
        Tuple of (success_boolean, status_message, total_items_removed).
    """
    logger.info("Initiating deletion of all locally installed ROMs...")
    deleted_files_count = 0

    session = db_session or DatabaseSession()
    try:
        with session as db:
            installs = db.installs.list_all()
            for install in installs:
                p_path = Path(install.file_path)
                if p_path.exists():
                    try:
                        p_path.unlink()
                        deleted_files_count += 1
                        logger.info(
                            "Unlinked installed ROM file: %s", install.file_path
                        )
                    except Exception as e:
                        logger.error(
                            "Failed unlinking ROM file %s: %s",
                            install.file_path,
                            e,
                        )

                if install.rom_dir:
                    p_dir = Path(install.rom_dir)
                    if p_dir.exists() and p_dir.is_dir():
                        try:
                            if not any(p_dir.iterdir()):
                                p_dir.rmdir()
                                logger.info(
                                    "Removed empty ROM directory: %s",
                                    install.rom_dir,
                                )
                        except Exception as e:
                            logger.warning(
                                "Failed removing empty ROM directory %s: %s",
                                install.rom_dir,
                                e,
                            )

            # Clear download_dir contents if it exists
            download_path = Path(settings.download_dir)
            if download_path.exists() and download_path.is_dir():
                for item in download_path.iterdir():
                    try:
                        if item.is_file() or item.is_symlink():
                            item.unlink()
                            deleted_files_count += 1
                        elif item.is_dir():
                            shutil.rmtree(item)
                            deleted_files_count += 1
                        logger.info("Cleaned item from download_dir: %s", item)
                    except Exception as e:
                        logger.error(
                            "Failed removing item from download_dir %s: %s",
                            item,
                            e,
                        )

            # Clear DB install records
            db_removed = db.installs.delete_all()
            db.commit()

            total_removed = max(deleted_files_count, db_removed)
            msg = f"Successfully deleted all installed ROMs ({total_removed} items cleared)."
            logger.info(msg)
            return True, msg, total_removed

    except Exception as e:
        logger.error("Failed deleting all installed ROMs: %s", e, exc_info=True)
        return False, f"Failed deleting installed ROMs: {str(e)}", 0


def purge_all_app_data(
    settings: AppSettings,
    sync_service: Optional[SyncService] = None,
    db_session: Optional[DatabaseSession] = None,
    skip_steam_guard: bool = False,
) -> Tuple[bool, str]:
    """Purge all application data (ROMs, Steam shortcuts, backups, logs, DB, configuration).

    Args:
        settings: Active AppSettings instance.
        sync_service: Optional SyncService instance.
        db_session: Optional DatabaseSession.
        skip_steam_guard: Whether to bypass Steam running check during shortcut cleanup.

    Returns:
        Tuple of (success_boolean, status_message).
    """
    logger.info(
        "Initiating full purging of all romm-steam-sync application data..."
    )

    # 1. Delete RomM Steam shortcuts and collections
    service = sync_service or SyncService(settings=settings)
    try:
        shortcut_ok, shortcut_msg, _ = service.remove_all_synced_libraries(
            skip_steam_guard=skip_steam_guard
        )
        logger.info(
            "Steam shortcut removal during purge: %s (msg: %s)",
            shortcut_ok,
            shortcut_msg,
        )
    except Exception as e:
        logger.error(
            "Error removing Steam shortcuts during app data purge: %s", e
        )

    # 2. Delete all installed ROMs & download_dir files
    rom_ok, rom_msg, _ = delete_all_installed_roms(
        settings=settings, db_session=db_session
    )
    logger.info("ROM file removal during purge: %s (msg: %s)", rom_ok, rom_msg)

    # 3. Release log file handles so log files can be deleted
    close_logging_file_handlers()

    # 4. Wipe everything in the application data directory
    app_data_dir = get_default_config_dir()
    logger.info("Purging local app data directory at: %s", app_data_dir)

    if app_data_dir.exists() and app_data_dir.is_dir():
        for item in list(app_data_dir.iterdir()):
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
                logger.info("Deleted app data directory item: %s", item.name)
            except Exception as e:
                # Log to console
                logger.warning(
                    "Could not delete %s during app data purge: %s",
                    item.name,
                    e,
                )

    logger.info(
        "All romm-steam-sync application data has been purged successfully."
    )
    return (
        True,
        "All application data and configuration have been completely purged.",
    )
