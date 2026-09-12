"""CLI entry point for romm-steam-sync-launcher."""

import argparse
import logging
import multiprocessing

from romm_steam_sync.launcher.app import LauncherWindow
from romm_steam_sync.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Parse command-line arguments and launch the game download/execution window."""
    multiprocessing.freeze_support()
    setup_logging()
    parser = argparse.ArgumentParser(description="RomM Steam Launcher Wrapper")
    parser.add_argument(
        "--launcher",
        action="store_true",
        help="Launcher execution flag",
    )
    parser.add_argument(
        "--rom-id",
        type=int,
        required=True,
        help="RomM ROM ID to download/launch",
    )
    parser.add_argument(
        "--platform", type=str, default="", help="RomM Platform Slug"
    )

    args, _ = parser.parse_known_args()

    logger.info(
        "Starting Launcher CLI wrapper with rom_id=%s, platform=%s",
        args.rom_id,
        args.platform,
    )

    app = LauncherWindow(rom_id=args.rom_id, platform_slug=args.platform)
    app.mainloop()


if __name__ == "__main__":
    main()
