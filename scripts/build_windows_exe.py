"""Build automation script for packaging romm-steam-sync Windows executables.

Executes a two-phase PyInstaller compilation and packaging pipeline:
1. Builds romm-steam-sync-launcher.exe (windowed standalone launcher).
2. Builds romm-steam-sync.exe (main GUI application, embedding the launcher).
3. Packages romm-steam-sync.exe into portable release archive:
   romm-steam-sync-v<version>-x86_64.zip.
"""

import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from romm_steam_sync.version import __version__

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger("build_windows_exe")



def kill_running_instances() -> None:
    """Terminate any lingering romm-steam-sync instances locking the binaries."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/IM", "romm-steam-sync*.exe", "/T"],
                capture_output=True,
                check=False,
            )
    except Exception as e:
        logger.debug("No existing processes needed termination: %s", e)


def clean_build_directories(project_root: Path) -> None:
    """Remove prior build artifacts and temporary compilation directories.

    Args:
        project_root: Path to the root of the repository.
    """
    kill_running_instances()
    build_dir = project_root / "build"
    if build_dir.exists():
        logger.info("Cleaning build directory: %s", build_dir)
        shutil.rmtree(build_dir, ignore_errors=True)


def build_spec(spec_file: Path) -> None:
    """Execute PyInstaller compilation for a given spec file.

    Args:
        spec_file: Path to the .spec file to execute.

    Raises:
        RuntimeError: If the PyInstaller compilation command fails.
    """
    logger.info("Starting PyInstaller compilation for %s...", spec_file.name)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_file),
        "--noconfirm",
    ]
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"PyInstaller build failed for {spec_file.name} with return code {result.returncode}"
        )
    logger.info("Successfully completed PyInstaller build for %s", spec_file.name)


def format_file_size(size_bytes: int) -> str:
    """Format byte count into human-readable megabytes.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Formatted size string (e.g. '42.5 MB').
    """
    mb = size_bytes / (1024 * 1024)
    return f"{mb:.2f} MB"


def main() -> None:
    """Orchestrate two-phase build of launcher and main GUI executables."""
    project_root = Path(__file__).resolve().parent.parent
    os.chdir(project_root)

    dist_dir = project_root / "dist"
    windows_dist_dir = dist_dir / "windows"
    windows_dist_dir.mkdir(parents=True, exist_ok=True)

    launcher_spec = project_root / "romm-steam-sync-launcher.spec"
    app_spec = project_root / "romm-steam-sync.spec"

    dist_launcher = dist_dir / "romm-steam-sync-launcher.exe"
    dist_app = dist_dir / "romm-steam-sync.exe"

    final_launcher = windows_dist_dir / "romm-steam-sync-launcher.exe"
    final_app = windows_dist_dir / "romm-steam-sync.exe"

    logger.info("Target Project Root: %s", project_root)
    logger.info("Windows Output Directory: %s", windows_dist_dir)

    # Clean intermediate build cache
    clean_build_directories(project_root)

    # Clean previous zip archives or legacy versioned binaries in windows dist
    for pattern in ["*.zip", "romm-steam-sync*-v*.exe", "romm-steam-sync-v*.exe"]:
        for item in windows_dist_dir.glob(pattern):
            if item.is_file():
                item.unlink()

    # Phase 1: Build romm-steam-sync-launcher.exe
    logger.info("=== Phase 1: Building romm-steam-sync-launcher.exe ===")
    build_spec(launcher_spec)
    if not dist_launcher.is_file():
        raise FileNotFoundError(
            f"Expected launcher executable was not created: {dist_launcher}"
        )
    shutil.copy2(dist_launcher, final_launcher)
    logger.info(
        "Launcher executable created: %s (%s)",
        final_launcher,
        format_file_size(final_launcher.stat().st_size),
    )

    # Phase 2: Build romm-steam-sync.exe (bundles launcher binary)
    logger.info("=== Phase 2: Building romm-steam-sync.exe ===")
    build_spec(app_spec)
    if not dist_app.is_file():
        raise FileNotFoundError(
            f"Expected main application executable was not created: {dist_app}"
        )
    shutil.copy2(dist_app, final_app)
    logger.info(
        "Main application executable created: %s (%s)",
        final_app,
        format_file_size(final_app.stat().st_size),
    )

    # Phase 3: Create portable release zip archive containing romm-steam-sync.exe
    logger.info("=== Phase 3: Creating portable release zip archive ===")
    version_str = f"v{__version__}"
    release_zip = windows_dist_dir / f"romm-steam-sync-{version_str}-windows-x86_64.zip"

    with zipfile.ZipFile(release_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(final_app, arcname="romm-steam-sync.exe")
    logger.info(
        "Release zip created: %s (%s)",
        release_zip.name,
        format_file_size(release_zip.stat().st_size),
    )

    # Clean intermediate root dist files to keep dist root tidy
    for item in [dist_launcher, dist_app]:
        if item.is_file():
            item.unlink()

    # Clean any legacy root files from previous runs
    for item in dist_dir.glob("romm-steam-sync*"):
        if item.is_file():
            item.unlink()

    logger.info("=== Windows Build Complete ===")
    logger.info(
        "Output artifacts generated in %s: %s, %s, %s",
        windows_dist_dir,
        final_app.name,
        final_launcher.name,
        release_zip.name,
    )


if __name__ == "__main__":
    main()
