"""One-time migration script seeding Gavel save-sync baselines into SQLite database."""

import logging
from pathlib import Path
import sys

# Ensure src/ directory is in sys.path when script is executed directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.config import AppSettings
from romm_steam_sync.domain import RomSaveSyncState
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.service_layer.save_strategies import (
    calculate_save_hash,
    get_save_strategy,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("migrate_gavel_baselines")


def migrate_baselines() -> int:
    """Scan local installed saves and RomM server saves to seed Gavel baseline records."""
    logger.info("Starting one-time Gavel save-sync baseline migration...")

    settings = AppSettings.load()
    client = None
    if settings.romm_url and settings.api_key:
        try:
            client = RomMApiClient(settings.romm_url, api_key=settings.api_key)
            logger.info("Authenticated with RomM server at %s", settings.romm_url)
        except Exception as e:
            logger.warning("Could not authenticate with RomM server (%s). Seed will run locally: %s", settings.romm_url, e)

    seeded_count = 0
    with DatabaseSession() as db:
        installs = db.installs.list_all()
        logger.info("Found %d installed ROM records in database.", len(installs))

        for install in installs:
            rom_id = install.rom_id
            rom = db.roms.get(rom_id)
            if not rom:
                logger.debug("No ROM entry found for install rom_id %s, skipping.", rom_id)
                continue

            platform_slug = rom.platform_slug or ""
            rom_path = install.file_path

            strategy = get_save_strategy(platform_slug=platform_slug)
            existing_local, _ = strategy.find_local_save_file(
                rom_path=rom_path,
                platform_slug=platform_slug,
                configured_retroarch_path=settings.retroarch_path,
            )

            if not existing_local or not existing_local.exists():
                logger.debug("No local save file found for ROM %s ('%s').", rom_id, rom.name)
                continue

            save_name = existing_local.name
            local_hash = calculate_save_hash(str(existing_local))
            local_size = existing_local.stat().st_size
            local_mtime = existing_local.stat().st_mtime

            remote_save = None
            if client:
                try:
                    remote_saves = client.get_saves(rom_id, slot=settings.default_slot or "autosave")
                    if remote_saves:
                        remote_save = remote_saves[0]
                except Exception as e:
                    logger.debug("Failed querying remote saves for rom_id %s: %s", rom_id, e)

            server_hash = remote_save.get("content_hash") if remote_save else None
            tracked_id = remote_save.get("id") if remote_save else None

            state = db.save_sync_states.get(rom_id) or RomSaveSyncState(
                rom_id=rom_id, active_slot=settings.default_slot or "autosave"
            )

            state.adopt_baseline(
                file_name=save_name,
                last_sync_hash=local_hash,
                last_sync_server_hash=server_hash,
                last_sync_local_size=local_size,
                last_sync_local_mtime=local_mtime,
                tracked_save_id=tracked_id,
            )

            db.save_sync_states.add(state)
            seeded_count += 1
            logger.info(
                "Seeded Gavel baseline for ROM %s ('%s') -> %s (hash: %s, size: %d bytes)",
                rom_id,
                rom.name,
                save_name,
                local_hash[:8] + "..." if local_hash else "None",
                local_size,
            )

        db.commit()

    logger.info("Successfully completed Gavel baseline migration! Seeded %d save records.", seeded_count)
    return seeded_count


if __name__ == "__main__":
    migrate_baselines()
