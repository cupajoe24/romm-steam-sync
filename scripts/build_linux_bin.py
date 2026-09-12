"""Build automation script for packaging romm-steam-sync Linux executables.

Executes a two-phase PyInstaller compilation and packaging pipeline:
1. Builds romm-steam-sync-launcher standalone ELF executable.
2. Builds romm-steam-sync main GUI application (embedding the launcher).
3. Packages romm-steam-sync into portable release archive:
   romm-steam-sync-v<version>-x86_64.tar.gz.

If executed on a Windows host, the script automatically delegates execution to WSL.
"""

import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

from romm_steam_sync.version import __version__

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger("build_linux_bin")


def clean_build_directories(project_root: Path) -> None:
    """Remove prior build artifacts and temporary compilation directories.

    Args:
        project_root: Path to the root of the repository.
    """
    build_dir = project_root / "build"
    if build_dir.exists():
        logger.info("Cleaning build directory: %s", build_dir)
        shutil.rmtree(build_dir, ignore_errors=True)


def build_spec(spec_file: Path) -> None:
    """Execute PyInstaller compilation for a given spec file.

    Args:
        spec_file: Path to the .spec file to execute.

    Raises:
        RuntimeError: If PyInstaller compilation fails.
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


def run_in_wsl(project_root: Path) -> None:
    """Delegate the Linux binary build to WSL from a Windows host environment.

    Args:
        project_root: Path to the root of the repository.

    Raises:
        RuntimeError: If WSL is not installed or if the WSL build process fails.
    """
    logger.info("Windows host detected. Delegating Linux build to WSL...")
    if not shutil.which("wsl"):
        raise RuntimeError(
            "WSL (Windows Subsystem for Linux) is required to build Linux binaries "
            "from a Windows environment. Please install WSL or run this script in Linux."
        )

    drive = project_root.drive[0].lower()
    rest = project_root.as_posix()[len(project_root.drive):]
    wsl_project_root = f"/mnt/{drive}{rest}"

    logger.info("WSL Project Path: %s", wsl_project_root)

    wsl_script = (
        f"set -e\n"
        f"cd '{wsl_project_root}'\n"
        f"if [ ! -d '.venv_linux' ]; then\n"
        f"    echo '[WSL] Creating Linux virtual environment in .venv_linux...'\n"
        f"    PYTHON_CMD='python3'\n"
        f"    if command -v python3.9 >/dev/null 2>&1; then\n"
        f"        PYTHON_CMD='python3.9'\n"
        f"    fi\n"
        f"    $PYTHON_CMD -m venv .venv_linux\n"
        f"    .venv_linux/bin/python -m pip install --upgrade pip setuptools wheel\n"
        f"    .venv_linux/bin/python -m pip install -e '.[dev]' pyinstaller\n"
        f"fi\n"
        f"echo '[WSL] Executing Linux build inside WSL...'\n"
        f".venv_linux/bin/python scripts/build_linux_bin.py\n"
    )

    build_process = subprocess.run(["wsl", "bash", "-c", wsl_script], check=False)
    if build_process.returncode != 0:
        raise RuntimeError(
            f"Linux build inside WSL failed with exit code {build_process.returncode}."
        )


def main() -> None:
    """Orchestrate build of Linux binaries and packaging archive."""
    project_root = Path(__file__).resolve().parent.parent

    # If invoked on Windows, automatically delegate build execution to WSL
    if sys.platform == "win32":
        run_in_wsl(project_root)
        return

    os.chdir(project_root)

    dist_dir = project_root / "dist"
    linux_dist_dir = dist_dir / "linux"
    linux_dist_dir.mkdir(parents=True, exist_ok=True)

    launcher_spec = project_root / "romm-steam-sync-launcher.spec"
    app_spec = project_root / "romm-steam-sync.spec"

    dist_launcher = dist_dir / "romm-steam-sync-launcher"
    dist_app = dist_dir / "romm-steam-sync"

    final_launcher = linux_dist_dir / "romm-steam-sync-launcher"
    final_app = linux_dist_dir / "romm-steam-sync"

    logger.info("Target Project Root: %s", project_root)
    logger.info("Linux Output Directory: %s", linux_dist_dir)

    # Clean intermediate build cache
    clean_build_directories(project_root)

    # Clean previous tarball archives or legacy versioned binaries in linux dist
    for pattern in ["*.tar.gz", "romm-steam-sync-v*", "romm-steam-sync-launcher-v*"]:
        for item in linux_dist_dir.glob(pattern):
            if item.is_file():
                item.unlink()

    # Phase 1: Build romm-steam-sync-launcher
    logger.info("=== Phase 1: Building romm-steam-sync-launcher ===")
    build_spec(launcher_spec)
    if not dist_launcher.is_file():
        raise FileNotFoundError(
            f"Expected launcher binary was not created: {dist_launcher}"
        )
    # Stage into linux_dist_dir and keep copy in dist_dir for main spec bundling
    shutil.copy2(dist_launcher, final_launcher)
    os.chmod(final_launcher, 0o755)
    logger.info(
        "Launcher binary created: %s (%s)",
        final_launcher,
        format_file_size(final_launcher.stat().st_size),
    )

    # Phase 2: Build romm-steam-sync (bundles launcher binary)
    logger.info("=== Phase 2: Building romm-steam-sync ===")
    build_spec(app_spec)
    if not dist_app.is_file():
        raise FileNotFoundError(
            f"Expected main application binary was not created: {dist_app}"
        )
    shutil.copy2(dist_app, final_app)
    os.chmod(final_app, 0o755)
    logger.info(
        "Main application binary created: %s (%s)",
        final_app,
        format_file_size(final_app.stat().st_size),
    )

    # Phase 3: Create portable release tarball containing romm-steam-sync
    logger.info("=== Phase 3: Creating portable release tarball ===")
    version_str = f"v{__version__}"
    release_tarball = linux_dist_dir / f"romm-steam-sync-{version_str}-x86_64.tar.gz"

    with tarfile.open(release_tarball, "w:gz") as tar:
        tar.add(final_app, arcname="romm-steam-sync")
    logger.info(
        "Release tarball created: %s (%s)",
        release_tarball.name,
        format_file_size(release_tarball.stat().st_size),
    )

    # Clean intermediate root dist files to keep dist root tidy
    for item in [dist_launcher, dist_app]:
        if item.is_file():
            item.unlink()

    # Clean any legacy root files from previous runs
    for item in dist_dir.glob("romm-steam-sync*"):
        if item.is_file():
            item.unlink()

    logger.info("=== Linux Build Complete ===")
    logger.info(
        "Output artifacts generated in %s: %s, %s, %s",
        linux_dist_dir,
        final_app.name,
        final_launcher.name,
        release_tarball.name,
    )


if __name__ == "__main__":
    main()
