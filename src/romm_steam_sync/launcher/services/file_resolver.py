"""Local file resolver for discovering, matching, and verifying ROM installs."""

from collections.abc import Set
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Optional

from romm_steam_sync.domain import (
    RomInstall,
    detect_launch_file,
    extract_disc_identifier,
    titles_match,
)
from romm_steam_sync.service_layer.db_session import DatabaseSession

logger = logging.getLogger(__name__)


class LocalRomResolver:
    """Service to scan local storage, resolve existing ROM files, and manage install records."""

    def __init__(self, db_session: Optional[DatabaseSession] = None):
        """Initialize LocalRomResolver.

        Args:
            db_session: Optional database session provider.
        """
        self.db_session = db_session or DatabaseSession()

    def resolve_local_rom(
        self,
        rom_id: int,
        rom_name: str,
        file_name: str,
        platform_slug: str,
        download_dir: str,
    ) -> Optional[Path]:
        """Check for existing ROM files locally and auto-register installs if found.

        Args:
            rom_id: Unique RomM ROM identifier.
            rom_name: Canonical name of the ROM.
            file_name: Expected filename of the ROM file or archive.
            platform_slug: Target platform identifier.
            download_dir: Base directory path for downloaded ROMs.

        Returns:
            Resolved local Path if found and verified, None otherwise.
        """
        with self.db_session as db:
            install_entity = db.installs.get(rom_id)

        if install_entity and install_entity.file_path and Path(install_entity.file_path).exists():
            local_path = Path(install_entity.file_path)
            logger.info("ROM file found via database install record: %s", local_path)
            return local_path

        local_path = self._scan_disk_for_rom(
            rom_id=rom_id,
            rom_name=rom_name,
            file_name=file_name,
            platform_slug=platform_slug,
            download_dir=download_dir,
        )

        if local_path and local_path.exists():
            logger.info("ROM file found locally at: %s", local_path)
            if not install_entity:
                self._auto_register_install(rom_id, local_path)
            return local_path

        logger.info("ROM file not found locally for rom_id %s", rom_id)
        return None

    def _scan_disk_for_rom(
        self,
        rom_id: int,
        rom_name: str,
        file_name: str,
        platform_slug: str,
        download_dir: str,
    ) -> Optional[Path]:
        """Scan disk directory structure for matching ROM files.

        Args:
            rom_id: ROM ID to scan for.
            rom_name: ROM canonical name.
            file_name: Expected filename.
            platform_slug: Platform identifier.
            download_dir: Base downloads folder path.

        Returns:
            Resolved Path if found, None otherwise.
        """
        download_base = Path(download_dir)
        p_folder = download_base / (platform_slug or "downloads")
        if not p_folder.exists():
            return None

        other_installed_paths = self._get_other_installed_paths(rom_id)

        if file_name:
            cand = p_folder / Path(file_name).name
            if cand.exists() and cand.is_file():
                return cand

            file_stem = Path(file_name).stem

            # 1. Check dedicated game folder (p_folder / file_stem)
            game_folder = p_folder / file_stem
            if game_folder.is_dir():
                folder_files = [f for f in game_folder.rglob("*") if f.is_file()]
                if folder_files:
                    return detect_launch_file(folder_files, preferred_stem=file_stem)

            # 2. Check loose files or other matching subdirectories
            target_disc = extract_disc_identifier(file_stem)
            candidates = []
            for item in p_folder.iterdir():
                try:
                    item_res = str(item.resolve()).lower()
                except Exception as e:
                    logger.debug("Failed resolving candidate path %s: %s", item, e)
                    item_res = str(item).lower()

                if item_res in other_installed_paths:
                    continue

                if item.is_file():
                    if item.stem.lower() == file_stem.lower() or titles_match(file_stem, item.stem):
                        if target_disc:
                            item_disc = extract_disc_identifier(item.stem)
                            if item_disc != target_disc:
                                continue
                        candidates.append(item)
                elif item.is_dir():
                    if item.name.lower() == file_stem.lower() or titles_match(file_stem, item.name):
                        if target_disc:
                            item_disc = extract_disc_identifier(item.name)
                            if item_disc != target_disc:
                                continue
                        sub_files = [
                            f for f in item.rglob("*")
                            if f.is_file() and str(f.resolve()).lower() not in other_installed_paths
                        ]
                        if sub_files:
                            sub_launch = detect_launch_file(sub_files, preferred_stem=file_stem)
                            if sub_launch and (
                                sub_launch.stem.lower() == file_stem.lower()
                                or titles_match(file_stem, sub_launch.stem)
                            ):
                                if target_disc:
                                    sub_disc = extract_disc_identifier(sub_launch.stem)
                                    if sub_disc != target_disc:
                                        continue
                                candidates.append(sub_launch)

            if candidates:
                exact = [c for c in candidates if c.stem.lower() == file_stem.lower()]
                if exact:
                    return detect_launch_file(exact, preferred_stem=file_stem)
                return detect_launch_file(candidates, preferred_stem=file_stem)

        else:
            candidates = []
            for item in p_folder.iterdir():
                try:
                    item_res = str(item.resolve()).lower()
                except Exception as e:
                    logger.debug("Failed resolving candidate path %s: %s", item, e)
                    item_res = str(item).lower()

                if item_res in other_installed_paths:
                    continue

                if item.is_file() and (
                    item.stem.lower() in rom_name.lower() or titles_match(rom_name, item.stem)
                ):
                    candidates.append(item)
                elif item.is_dir() and (
                    item.name.lower() in rom_name.lower() or titles_match(rom_name, item.name)
                ):
                    sub_files = [
                        f for f in item.rglob("*")
                        if f.is_file() and str(f.resolve()).lower() not in other_installed_paths
                    ]
                    if sub_files:
                        sub_launch = detect_launch_file(sub_files, preferred_stem=rom_name)
                        if sub_launch:
                            candidates.append(sub_launch)

            if candidates:
                return detect_launch_file(candidates, preferred_stem=rom_name)

        return None

    def _get_other_installed_paths(self, current_rom_id: int) -> Set[str]:
        """Collect paths of files installed for other ROMs to avoid false matching.

        Args:
            current_rom_id: ID of the current ROM being inspected.

        Returns:
            Set of lowercase resolved file paths.
        """
        other_installed_paths: Set[str] = set()
        with self.db_session as db:
            for inst in db.installs.list_all():
                if inst.rom_id != current_rom_id and inst.file_path:
                    try:
                        other_installed_paths.add(str(Path(inst.file_path).resolve()).lower())
                    except Exception as e:
                        logger.debug("Failed resolving installed path %s: %s", inst.file_path, e)
                        other_installed_paths.add(inst.file_path.lower())
        return other_installed_paths

    def _auto_register_install(self, rom_id: int, local_path: Path) -> None:
        """Auto-register a discovered file as a RomInstall in the database.

        Args:
            rom_id: Unique ROM identifier.
            local_path: Path to the discovered launchable file.
        """
        try:
            with self.db_session as db:
                db.installs.add(
                    RomInstall(
                        rom_id=rom_id,
                        file_path=str(local_path),
                        rom_dir=str(local_path.parent),
                        launchable=True,
                        installed_at=datetime.now(timezone.utc),
                    )
                )
                db.commit()
                logger.info("Auto-registered RomInstall record for rom_id %s -> %s", rom_id, local_path)
        except Exception as e:
            logger.debug("Failed auto-registering RomInstall in resolver: %s", e)
