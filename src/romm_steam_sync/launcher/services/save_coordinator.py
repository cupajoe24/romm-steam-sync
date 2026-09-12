"""Save file and playtime coordination service for RomM launcher."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil
import time
from typing import Any, Dict, Optional, Tuple

import requests

from romm_steam_sync.adapters.retroarch_launcher import DEFAULT_CORE_MAPPINGS
from romm_steam_sync.adapters.romm_api import RomMApiClient, RomMTimeoutError
from romm_steam_sync.config import AppSettings
from romm_steam_sync.service_layer.save_strategies.shared_memory_card import (
    SharedMemoryCardStrategy,
    get_app_local_memcard_path,
    get_retroarch_memcard_path,
)
from romm_steam_sync.service_layer.save_sync import (
    SaveSyncEngine,
    find_local_save_file,
    get_save_strategy,
    quarantine_local_save,
)

logger = logging.getLogger(__name__)


class SaveCoordinator:
    """Coordinates pre-launch and post-launch save file synchronization and playtime reporting."""

    def __init__(self, settings: Optional[AppSettings] = None):
        """Initialize SaveCoordinator.

        Args:
            settings: Optional AppSettings instance.
        """
        self.settings = settings or AppSettings.load()

    def sync_pre_launch(
        self,
        rom_id: int,
        local_file_path: str,
        platform_slug: str,
        client: Optional[RomMApiClient] = None,
    ) -> Tuple[str, str, Optional[Dict[str, Any]], Optional[Path]]:
        """Perform pre-launch save sync evaluation.

        Args:
            rom_id: RomM ROM identifier.
            local_file_path: Path to the local ROM file.
            platform_slug: Platform identifier.
            client: Optional RomMApiClient instance.

        Returns:
            Tuple of (action, message, remote_save_dict, save_target_path).
            Action can be 'DOWNLOAD', 'UPLOAD', 'NO_OP', 'CONFLICT', 'BYPASS', or 'UNREACHABLE'.
        """
        core_name = (
            self.settings.core_mappings.get(platform_slug)
            or DEFAULT_CORE_MAPPINGS.get(platform_slug, "")
        )

        if not getattr(self.settings, "save_sync_enabled", True):
            logger.info("Save syncing disabled; bypassing pre-launch sync for rom_id %s", rom_id)
            strategy = get_save_strategy(core_name=core_name, platform_slug=platform_slug)
            existing_local, default_target = strategy.find_local_save_file(
                rom_path=local_file_path,
                platform_slug=platform_slug,
                configured_retroarch_path=self.settings.retroarch_path,
                core_name=core_name,
            )
            if isinstance(strategy, SharedMemoryCardStrategy) and existing_local and existing_local.exists():
                try:
                    default_target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(existing_local, default_target)
                    logger.info("Offline launch: staged local memory card %s to RetroArch %s", existing_local, default_target)
                except Exception as e:
                    logger.warning("Could not stage offline memory card: %s", e)
            return "BYPASS", "Save syncing disabled in settings.", None, default_target

        api_client = client or RomMApiClient(
            base_url=self.settings.romm_url,
            api_key=self.settings.api_key,
        )

        try:
            action, msg, remote_save, save_target = SaveSyncEngine.sync_pre_launch(
                rom_id=rom_id,
                rom_path=local_file_path,
                platform_slug=platform_slug,
                client=api_client,
                configured_retroarch_path=self.settings.retroarch_path,
                slot=self.settings.default_slot,
                core_name=core_name,
            )
            return action, msg, remote_save, save_target
        except (RomMTimeoutError, requests.exceptions.RequestException) as e:
            logger.warning("RomM server unreachable during pre-launch save sync: %s", e)
            _, default_target = find_local_save_file(
                local_file_path,
                platform_slug=platform_slug,
                configured_retroarch_path=self.settings.retroarch_path,
                core_name=core_name,
            )
            return "UNREACHABLE", str(e), None, default_target
        except Exception as e:
            logger.error("Unexpected error during pre-launch save sync: %s", e)
            _, default_target = find_local_save_file(
                local_file_path,
                platform_slug=platform_slug,
                configured_retroarch_path=self.settings.retroarch_path,
                core_name=core_name,
            )
            return "ERROR", str(e), None, default_target

    def resolve_conflict_choice(
        self,
        choice: str,
        rom_id: int,
        remote_save: Optional[Dict[str, Any]],
        save_target: Path,
        platform_slug: str,
        client: Optional[RomMApiClient] = None,
    ) -> Path:
        """Apply user's conflict resolution choice ('remote' or 'local').

        Args:
            choice: Either 'remote' or 'local'.
            rom_id: Unique RomM ROM identifier.
            remote_save: Remote save metadata dictionary if available.
            save_target: Target save file path.
            platform_slug: Platform identifier.
            client: Optional RomMApiClient instance.

        Returns:
            Resolved save target Path.
        """
        api_client = client or RomMApiClient(
            base_url=self.settings.romm_url,
            api_key=self.settings.api_key,
        )

        try:
            if choice == "remote" and remote_save:
                save_id = remote_save.get("id")
                if save_id:
                    quarantine_local_save(str(save_target))
                    api_client.download_save_content(save_id, str(save_target))
            elif choice == "local" and save_target.exists():
                save_id = remote_save.get("id") if remote_save else None
                api_client.upload_save(rom_id, str(save_target), save_id=save_id, slot=self.settings.default_slot)

            core_name = (
                self.settings.core_mappings.get(platform_slug)
                or DEFAULT_CORE_MAPPINGS.get(platform_slug, "")
            )
            strategy = get_save_strategy(core_name=core_name, platform_slug=platform_slug)
            if isinstance(strategy, SharedMemoryCardStrategy):
                card_filename = strategy.resolve_card_filename(
                    remote_save, core_name=core_name, platform_slug=platform_slug
                )
                ra_card_file = get_retroarch_memcard_path(
                    self.settings.retroarch_path, core_name, platform_slug, card_filename
                )
                if save_target.exists():
                    shutil.copy2(save_target, ra_card_file)
                    logger.info("Swapped chosen memory card %s to RetroArch %s", save_target, ra_card_file)
                save_target = ra_card_file
        except Exception as e:
            logger.warning("Error resolving save conflict: %s", e)

        return save_target

    def sync_post_launch(
        self,
        rom_id: int,
        local_file_path: Optional[str],
        platform_slug: str,
        save_target: Optional[Path],
        session_start_time: Optional[datetime],
        session_start_mono: Optional[float],
        client: Optional[RomMApiClient] = None,
    ) -> None:
        """Perform post-launch save upload and playtime reporting.

        Args:
            rom_id: RomM ROM identifier.
            local_file_path: Path to the local ROM file.
            platform_slug: Platform identifier.
            save_target: Save target path used during game session.
            session_start_time: Start datetime for playtime tracking.
            session_start_mono: Monotonic start timestamp.
            client: Optional RomMApiClient instance.
        """
        try:
            # Brief pause to ensure OS filesystem flushes save file after process exit
            time.sleep(0.5)

            api_client = client or RomMApiClient(
                base_url=self.settings.romm_url,
                api_key=self.settings.api_key,
            )

            # 1. Ingest Play Session
            if session_start_time:
                session_end_time = datetime.now(timezone.utc)
                if session_start_mono is not None:
                    duration_ms = max(1000, int((time.monotonic() - session_start_mono) * 1000))
                else:
                    start_utc = (
                        session_start_time
                        if session_start_time.tzinfo is not None
                        else session_start_time.replace(tzinfo=timezone.utc)
                    )
                    duration_ms = max(1000, int((session_end_time - start_utc).total_seconds() * 1000))

                session_entry = {
                    "rom_id": rom_id,
                    "start_time": session_start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_time": session_end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "duration_ms": duration_ms,
                }
                try:
                    api_client.ingest_play_sessions(
                        device_id=self.settings.device_id,
                        sessions=[session_entry],
                    )
                except Exception as e:
                    logger.warning("Error ingesting play session to RomM for rom_id %s: %s", rom_id, e)

            # 2. Upload modified save file back to RomM
            if getattr(self.settings, "save_sync_enabled", True):
                core_name = (
                    self.settings.core_mappings.get(platform_slug)
                    or DEFAULT_CORE_MAPPINGS.get(platform_slug, "")
                )
                strategy = get_save_strategy(core_name=core_name, platform_slug=platform_slug)
                existing_local, default_target = strategy.find_local_save_file(
                    rom_path=str(local_file_path or ""),
                    platform_slug=platform_slug,
                    configured_retroarch_path=self.settings.retroarch_path,
                    core_name=core_name,
                )

                target_p = existing_local if (existing_local and existing_local.exists()) else (
                    save_target if (save_target and save_target.exists()) else default_target
                )

                logger.info("Executing post-launch save sync for rom_id %s (target_p: %s)", rom_id, target_p)
                success, msg = SaveSyncEngine.sync_post_launch(
                    rom_id,
                    str(target_p),
                    api_client,
                    slot=self.settings.default_slot,
                    platform_slug=platform_slug,
                    configured_retroarch_path=self.settings.retroarch_path,
                    core_name=core_name,
                    rom_path=str(local_file_path or ""),
                )
                if not success:
                    logger.warning("Post-launch save upload warning: %s", msg)
            else:
                # Offline mode: persist local RetroArch save back to app local storage
                core_name = (
                    self.settings.core_mappings.get(platform_slug)
                    or DEFAULT_CORE_MAPPINGS.get(platform_slug, "")
                )
                strategy = get_save_strategy(core_name=core_name, platform_slug=platform_slug)
                if isinstance(strategy, SharedMemoryCardStrategy):
                    rom_stem = Path(str(local_file_path or "")).stem
                    card_filename = strategy.resolve_card_filename(
                        core_name=core_name, platform_slug=platform_slug
                    )
                    ra_card_file = get_retroarch_memcard_path(
                        self.settings.retroarch_path, core_name, platform_slug, card_filename
                    )
                    local_card_file = get_app_local_memcard_path(
                        core_name, rom_stem, card_filename, platform_slug
                    )
                    if ra_card_file.exists():
                        try:
                            local_card_file.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(ra_card_file, local_card_file)
                            logger.info("Preserved offline memory card to local storage: %s", local_card_file)
                            try:
                                ra_card_file.unlink()
                            except Exception as del_err:
                                logger.debug("Could not unlink runtime memory card %s: %s", ra_card_file, del_err)
                        except Exception as e:
                            logger.warning("Could not preserve offline memory card: %s", e)
                logger.info("Save syncing disabled; skipped post-launch upload for rom_id %s", rom_id)
        except Exception as e:
            logger.error("Unhandled exception during post-launch save sync for rom_id %s: %s", rom_id, e)
