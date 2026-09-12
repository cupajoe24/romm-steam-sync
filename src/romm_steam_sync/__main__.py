"""Entry point for running module via `python -m romm_steam_sync` or standalone exe."""

import multiprocessing
import sys


def main() -> None:
    """Entry point dispatching to launcher or full GUI application."""
    multiprocessing.freeze_support()
    if "--rom-id" in sys.argv:
        from romm_steam_sync.launcher.__main__ import main as launcher_main

        launcher_main()
    else:
        from romm_steam_sync.ui.app import main as ui_main

        ui_main()


if __name__ == "__main__":
    main()

