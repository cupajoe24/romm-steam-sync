"""Service for downloading and extracting ROM files on demand."""

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Callable, Optional, Tuple

from romm_steam_sync.adapters.archive_extractor import ArchiveExtractor
from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.domain import RomInstall, should_extract_rom
from romm_steam_sync.launcher.formatters import format_size
from romm_steam_sync.service_layer.db_session import DatabaseSession

logger = logging.getLogger(__name__)


class RomDownloadService:
    """Handles downloading ROM files from RomM and extracting archives if needed."""

    def __init__(self, db_session: Optional[DatabaseSession] = None):
        """Initialize RomDownloadService.

        Args:
            db_session: Optional database session provider.
        """
        self.db_session = db_session or DatabaseSession()

    def download_rom(
        self,
        rom_id: int,
        rom_name: str,
        file_name: str,
        platform_slug: str,
        download_dir: str,
        romm_url: str,
        api_key: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        client: Optional[RomMApiClient] = None,
    ) -> Tuple[bool, Optional[Path], Optional[str]]:
        """Download ROM file from RomM, extract if disc-based archive, and record install in database.

        Args:
            rom_id: Unique RomM ROM identifier.
            rom_name: Canonical name of the ROM.
            file_name: Expected filename of the ROM or archive.
            platform_slug: Platform identifier.
            download_dir: Target base download directory.
            romm_url: RomM API base URL.
            api_key: RomM API key.
            progress_callback: Optional callback receiving (pct: float, message: str).
            client: Optional pre-configured RomMApiClient.

        Returns:
            Tuple of (success: bool, final_rom_path: Optional[Path], error_message: Optional[str]).
        """
        api_client = client or RomMApiClient(base_url=romm_url, api_key=api_key)

        dest_dir = Path(download_dir) / (platform_slug or "downloads")
        dest_filename = Path(file_name).name if file_name else f"{rom_name}.rom"
        target_path = dest_dir / dest_filename

        def api_progress(downloaded: int, total: int) -> None:
            pct = (downloaded / total) if total > 0 else 0.0
            pct_text = f"Downloading... {int(pct * 100)}% ({format_size(downloaded)} / {format_size(total)})"
            if progress_callback:
                progress_callback(pct, pct_text)

        logger.info("Initiating download for rom_id %s -> %s", rom_id, target_path)
        success = api_client.download_rom_content(
            rom_id,
            str(target_path),
            file_name=dest_filename,
            progress_callback=api_progress,
        )

        if not success or not target_path.exists():
            error_msg = "Could not download ROM file from RomM server. Please check your connection."
            logger.error("Failed to download ROM content for rom_id %s", rom_id)
            return False, None, error_msg

        final_rom_path = target_path
        final_rom_dir = dest_dir

        if should_extract_rom(platform_slug, target_path):
            extract_dir = dest_dir / target_path.stem
            extract_dir.mkdir(parents=True, exist_ok=True)
            final_rom_dir = extract_dir

            logger.info(
                "Platform '%s' is disc-based; extracting downloaded archive '%s' into '%s'...",
                platform_slug,
                target_path.name,
                extract_dir,
            )
            if progress_callback:
                progress_callback(1.0, f"Extracting {target_path.name}...")

            try:
                def extract_progress(msg: str) -> None:
                    if progress_callback:
                        progress_callback(1.0, msg)

                _, launch_file = ArchiveExtractor.extract_and_cleanup(
                    archive_path=target_path,
                    dest_dir=extract_dir,
                    preferred_stem=target_path.stem,
                    progress_callback=extract_progress,
                )
                final_rom_path = launch_file
                logger.info(
                    "Extraction complete for rom_id %s. Primary launch file: %s in directory %s",
                    rom_id,
                    final_rom_path,
                    extract_dir,
                )
            except Exception as e:
                logger.error("Failed extracting downloaded ROM archive for rom_id %s: %s", rom_id, e)
                return False, None, f"Failed extracting downloaded ROM archive:\n{e}"

        logger.info("ROM content ready at: %s", final_rom_path)
        self._record_install(rom_id, final_rom_path, final_rom_dir)
        return True, final_rom_path, None

    def _record_install(self, rom_id: int, rom_path: Path, rom_dir: Path) -> None:
        """Record the installed ROM in the database.

        Args:
            rom_id: ROM ID installed.
            rom_path: Path to the launchable ROM file.
            rom_dir: Directory enclosing the installed ROM.
        """
        try:
            with self.db_session as db:
                install_entity = RomInstall(
                    rom_id=rom_id,
                    file_path=str(rom_path),
                    rom_dir=str(rom_dir),
                    launchable=True,
                    installed_at=datetime.now(timezone.utc),
                )
                db.installs.add(install_entity)
                db.commit()
                logger.info("Saved RomInstall record for rom_id %s", rom_id)
        except Exception as e:
            logger.warning("Failed to persist RomInstall to DB: %s", e)
