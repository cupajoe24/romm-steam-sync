"""Archive extraction adapter for disc-based retro game archives."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from typing import Callable, List, Optional, Tuple, Union
import zipfile

from romm_steam_sync.adapters.retroarch.base import clean_subprocess_env
from romm_steam_sync.domain.disc_formats import (
    COMPOUND_ARCHIVE_SUFFIXES,
    IGNORED_EXTENSIONS,
    detect_launch_file,
    is_archive_file,
)

logger = logging.getLogger(__name__)


class ArchiveExtractorError(Exception):
    """Raised when archive extraction fails."""


class ZipSlipSecurityError(ArchiveExtractorError):
    """Raised when an archive member attempts a path traversal attack."""


class ArchiveExtractor:
    """Extracts compressed ROM archives with ZIP-slip protection and formats resolution."""

    @classmethod
    def extract_archive(
        cls,
        archive_path: Union[str, Path],
        dest_dir: Union[str, Path],
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> List[Path]:
        """Extract an archive (.zip, .7z, .tar, .tar.gz, etc.) into dest_dir safely.

        Args:
            archive_path: Path to the archive file on disk.
            dest_dir: Destination directory for extracted contents.
            progress_callback: Optional callback reporting extraction progress.

        Returns:
            List of Path objects for all extracted files.

        Raises:
            FileNotFoundError: If the archive file does not exist.
            ArchiveExtractorError: If extraction fails or format is unsupported.
            ZipSlipSecurityError: If an archive contains path traversal sequences.
        """
        archive_p = Path(archive_path).resolve()
        dest_p = Path(dest_dir).resolve()
        dest_p.mkdir(parents=True, exist_ok=True)

        if not archive_p.exists():
            raise FileNotFoundError(f"Archive file not found: {archive_p}")

        name_lower = archive_p.name.lower()
        logger.info(
            "Starting archive extraction for '%s' into '%s'",
            archive_p.name,
            dest_p,
        )

        if progress_callback:
            progress_callback(f"Extracting {archive_p.name}...")

        extracted: List[Path] = []

        if name_lower.endswith(".zip"):
            extracted = cls._extract_zip(archive_p, dest_p)
        elif name_lower.endswith(".7z"):
            extracted = cls._extract_7z(archive_p, dest_p)
        elif any(
            name_lower.endswith(suf) for suf in COMPOUND_ARCHIVE_SUFFIXES
        ) or name_lower.endswith((".tar", ".tgz", ".tbz2", ".txz")):
            extracted = cls._extract_tar(archive_p, dest_p)
        else:
            # Attempt zip first, then tar
            try:
                extracted = cls._extract_zip(archive_p, dest_p)
            except Exception as e_zip:
                logger.debug(
                    "Zip extraction fallback attempt failed for %s: %s",
                    archive_p.name,
                    e_zip,
                )
                try:
                    extracted = cls._extract_tar(archive_p, dest_p)
                except Exception as e_tar:
                    logger.error(
                        "Failed to extract unrecognized archive %s: %s / %s",
                        archive_p.name,
                        e_zip,
                        e_tar,
                    )
                    raise ArchiveExtractorError(
                        f"Unsupported or corrupted archive format: {archive_p.name}"
                    )

        logger.info("Extracted %d files from '%s'", len(extracted), archive_p.name)
        return extracted

    @classmethod
    def _extract_zip(cls, archive_path: Path, dest_dir: Path) -> List[Path]:
        """Extract a .zip file with ZIP-slip validation.

        Args:
            archive_path: Path to .zip archive.
            dest_dir: Destination extraction directory.

        Returns:
            List of extracted file Paths.

        Raises:
            ZipSlipSecurityError: If path traversal is detected.
            ArchiveExtractorError: If extraction fails.
        """
        extracted_files: List[Path] = []
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue

                    # Skip macOS metadata files
                    if (
                        member.filename.startswith("__MACOSX/")
                        or Path(member.filename).name.startswith("._")
                        or member.filename.endswith(".DS_Store")
                    ):
                        continue

                    # Validate path traversal (Zip Slip protection)
                    target_path = (dest_dir / member.filename).resolve()
                    if not cls._is_safe_path(dest_dir, target_path):
                        logger.error(
                            "ZIP-slip attempt detected in '%s': member '%s'",
                            archive_path.name,
                            member.filename,
                        )
                        raise ZipSlipSecurityError(
                            f"Path traversal detected in archive member: {member.filename}"
                        )

                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as source, open(target_path, "wb") as target:
                        shutil.copyfileobj(source, target)

                    extracted_files.append(target_path)
            return extracted_files
        except Exception as e:
            if isinstance(e, ArchiveExtractorError):
                raise
            logger.error("Failed extracting ZIP archive '%s': %s", archive_path.name, e)
            raise ArchiveExtractorError(
                f"Failed extracting ZIP archive '{archive_path.name}': {e}"
            ) from e

    @classmethod
    def _extract_7z(cls, archive_path: Path, dest_dir: Path) -> List[Path]:
        """Extract a .7z file using py7zr if available, or system 7z CLI.

        Args:
            archive_path: Path to .7z archive.
            dest_dir: Destination extraction directory.

        Returns:
            List of extracted file Paths.

        Raises:
            ZipSlipSecurityError: If path traversal is detected.
            ArchiveExtractorError: If extraction fails.
        """
        # 1. Try py7zr
        try:
            import py7zr

            extracted_files: List[Path] = []
            with py7zr.SevenZipFile(archive_path, mode="r") as sz:
                all_names = sz.getnames()
                safe_names = []
                for name in all_names:
                    # Skip macOS metadata
                    if (
                        name.startswith("__MACOSX/")
                        or Path(name).name.startswith("._")
                        or name.endswith(".DS_Store")
                    ):
                        continue
                    target_path = (dest_dir / name).resolve()
                    if not cls._is_safe_path(dest_dir, target_path):
                        logger.error(
                            "7z path traversal detected in '%s': member '%s'",
                            archive_path.name,
                            name,
                        )
                        raise ZipSlipSecurityError(
                            f"Path traversal detected in 7z member: {name}"
                        )
                    safe_names.append(name)

                sz.extract(path=dest_dir, targets=safe_names if safe_names else None)

                for name in safe_names:
                    target_path = dest_dir / name
                    if target_path.is_file():
                        extracted_files.append(target_path)
            return extracted_files

        except ImportError:
            logger.warning(
                "py7zr is not installed; attempting fallback to system 7z CLI"
            )
        except Exception as e:
            if isinstance(e, ArchiveExtractorError):
                raise
            logger.error("py7zr extraction error for '%s': %s", archive_path.name, e)
            raise ArchiveExtractorError(
                f"Failed extracting 7z archive '{archive_path.name}': {e}"
            ) from e

        # 2. Try system 7z CLI
        seven_zip_cli = shutil.which("7z") or shutil.which("7za")
        if not seven_zip_cli and os.name == "nt":
            candidates = [
                Path(r"C:\Program Files\7-Zip\7z.exe"),
                Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
            ]
            for cand in candidates:
                if cand.exists():
                    seven_zip_cli = str(cand)
                    break

        if seven_zip_cli:
            try:
                cmd = [seven_zip_cli, "x", "-y", f"-o{dest_dir}", str(archive_path)]
                logger.info("Running 7z CLI command: %s", " ".join(cmd))
                subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    env=clean_subprocess_env(),
                )
                # Find all files in dest_dir that were created/modified
                extracted_files = [
                    p
                    for p in dest_dir.rglob("*")
                    if p.is_file() and p.resolve() != archive_path.resolve()
                ]
                return extracted_files
            except Exception as e:
                logger.error(
                    "7z CLI execution failed for '%s': %s", archive_path.name, e
                )
                raise ArchiveExtractorError(
                    f"7-Zip CLI failed to extract '{archive_path.name}': {e}"
                ) from e

        raise ArchiveExtractorError(
            f"Cannot extract '{archive_path.name}': 'py7zr' is not installed and no '7z' CLI was found on system."
        )

    @classmethod
    def _extract_tar(cls, archive_path: Path, dest_dir: Path) -> List[Path]:
        """Extract a tar archive (.tar, .tar.gz, .tar.bz2, .tar.xz) with ZIP-slip validation.

        Args:
            archive_path: Path to tar archive.
            dest_dir: Destination extraction directory.

        Returns:
            List of extracted file Paths.

        Raises:
            ZipSlipSecurityError: If path traversal is detected.
            ArchiveExtractorError: If extraction fails.
        """
        extracted_files: List[Path] = []
        try:
            with tarfile.open(archive_path, "r:*") as tf:
                for member in tf.getmembers():
                    if member.isdir():
                        continue
                    if (
                        member.name.startswith("__MACOSX/")
                        or Path(member.name).name.startswith("._")
                        or member.name.endswith(".DS_Store")
                    ):
                        continue

                    target_path = (dest_dir / member.name).resolve()
                    if not cls._is_safe_path(dest_dir, target_path):
                        logger.error(
                            "Tar path traversal detected in '%s': member '%s'",
                            archive_path.name,
                            member.name,
                        )
                        raise ZipSlipSecurityError(
                            f"Path traversal detected in tar member: {member.name}"
                        )

                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    f_obj = tf.extractfile(member)
                    if f_obj:
                        with open(target_path, "wb") as target:
                            shutil.copyfileobj(f_obj, target)
                        extracted_files.append(target_path)
            return extracted_files
        except Exception as e:
            if isinstance(e, ArchiveExtractorError):
                raise
            logger.error("Failed extracting tar archive '%s': %s", archive_path.name, e)
            raise ArchiveExtractorError(
                f"Failed extracting tar archive '{archive_path.name}': {e}"
            ) from e

    @classmethod
    def extract_and_cleanup(
        cls,
        archive_path: Union[str, Path],
        dest_dir: Union[str, Path],
        preferred_stem: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[List[Path], Path]:
        """Extract archive to dest_dir, delete archive file from disk, and resolve primary launch file.

        Args:
            archive_path: Path to downloaded archive.
            dest_dir: Target extraction folder.
            preferred_stem: Optional preferred file stem for launch resolution.
            progress_callback: Optional callback for progress reporting.

        Returns:
            Tuple of (list_of_extracted_paths, primary_launch_file_path).

        Raises:
            ArchiveExtractorError: If extraction fails or archive is empty.
        """
        archive_p = Path(archive_path).resolve()
        dest_p = Path(dest_dir).resolve()

        extracted_files = cls.extract_archive(
            archive_p, dest_p, progress_callback=progress_callback
        )

        if not extracted_files:
            raise ArchiveExtractorError(
                f"Archive '{archive_p.name}' contained no extractable files."
            )

        # Identify primary launch file
        stem = preferred_stem or archive_p.stem
        launch_file = detect_launch_file(extracted_files, preferred_stem=stem)
        if not launch_file or not launch_file.exists():
            # Fallback to the first extracted file if detect_launch_file returned None
            launch_file = extracted_files[0]

        logger.info(
            "Selected primary launch file for '%s': %s", archive_p.name, launch_file
        )

        # Safely delete original archive from local disk
        try:
            if archive_p.exists() and archive_p.is_file():
                archive_p.unlink()
                logger.info(
                    "Deleted downloaded ROM archive '%s' from local storage.", archive_p
                )
        except Exception as e:
            logger.warning(
                "Could not delete downloaded ROM archive '%s': %s", archive_p, e
            )

        return extracted_files, launch_file

    @staticmethod
    def _is_safe_path(dest_dir: Path, target_path: Path) -> bool:
        """Check if target_path is within dest_dir to prevent Zip-Slip.

        Args:
            dest_dir: Base directory that must contain the target.
            target_path: Absolute destination path for extracted member.

        Returns:
            True if target_path resides inside dest_dir, False otherwise.
        """
        try:
            dest_resolved = dest_dir.resolve()
            target_resolved = target_path.resolve()
            return (
                target_resolved == dest_resolved
                or dest_resolved in target_resolved.parents
            )
        except Exception as e:
            logger.debug(
                "Error checking path safety for %s in %s: %s",
                target_path,
                dest_dir,
                e,
            )
            return False
