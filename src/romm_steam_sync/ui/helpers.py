"""Shared UI helper functions and abstractions for dialogs, auth, and progress."""

import logging
import os
import threading
from tkinter import filedialog
from typing import Any, Callable, Optional, Tuple

import customtkinter as ctk

from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.adapters.steamgriddb import SteamGridDbClient
from romm_steam_sync.adapters.wrapper_installer import install_wrapper
from romm_steam_sync.config import AppSettings
from romm_steam_sync.ui.components.timeout_modal import RomMTimeoutModal

logger = logging.getLogger(__name__)


def test_and_save_romm_credentials(
    settings: AppSettings,
    url: str,
    api_key: str,
    client_cls: Any = RomMApiClient,
    install_launcher: bool = False,
) -> Tuple[bool, str]:
    """Test connection to RomM server and persist validated credentials to settings.

    Args:
        settings: Active AppSettings instance.
        url: RomM server base URL string.
        api_key: RomM API key or bearer token.
        client_cls: Class or factory to instantiate RomMApiClient (allows test mocks).
        install_launcher: Whether to install launcher wrapper script on success.

    Returns:
        Tuple of (is_successful_boolean, message_string).
    """
    clean_url = url.strip()
    clean_key = api_key.strip()

    if not clean_url or clean_url.rstrip("/") in ("http:", "https:", "http://", "https://"):
        return False, "RomM Server URL is required."

    logger.info("Testing connection to RomM server at %s", clean_url)
    try:
        client = client_cls(
            base_url=clean_url,
            api_key=clean_key,
        )
        ok, msg = client.authenticate()
        if ok:
            logger.info("RomM server connection test passed: %s", msg)
            settings.romm_url = clean_url
            settings.api_key = clean_key
            settings.save()

            if install_launcher:
                try:
                    install_wrapper()
                except Exception as e:
                    logger.warning("Failed installing launcher wrapper during server setup: %s", e)

            return True, msg
        else:
            logger.warning("RomM connection test failed: %s", msg)
            return False, msg
    except Exception as e:
        logger.error("RomM connection test exception: %s", e)
        return False, str(e)


def verify_steamgriddb_key(api_key: str, client_cls: Any = SteamGridDbClient) -> Tuple[bool, str]:
    """Test user-entered SteamGridDB API key against SGDB API.

    Args:
        api_key: SteamGridDB API key to test.
        client_cls: Class or factory to instantiate SteamGridDbClient (allows test mocks).

    Returns:
        Tuple of (is_valid_boolean, message_string).
    """
    key = api_key.strip()
    if not key:
        return False, "Please enter an API Key to test."

    logger.info("Testing SteamGridDB API key...")
    try:
        client = client_cls(api_key=key)
        ok, msg = client.verify_api_key(key)
        if ok:
            logger.info("SteamGridDB API key validated successfully: %s", msg)
        else:
            logger.warning("SteamGridDB API key validation failed: %s", msg)
        return ok, msg
    except Exception as e:
        logger.error("Error testing SteamGridDB API key: %s", e)
        return False, f"Test failed: {e}"


def browse_retroarch_executable(parent: Any = None) -> Optional[str]:
    """Open platform-appropriate file dialog to locate RetroArch binary.

    Args:
        parent: Optional parent tkinter widget for dialog centering.

    Returns:
        Path string to selected executable, or None if cancelled.
    """
    file_types = (
        [
            ("RetroArch Executable", "retroarch.exe"),
            ("All Executables", "*.exe"),
            ("All Files", "*.*"),
        ]
        if os.name == "nt"
        else [("All Files", "*.*")]
    )
    try:
        chosen = filedialog.askopenfilename(
            parent=parent,
            title="Select RetroArch Executable",
            filetypes=file_types,
        )
        if chosen:
            logger.info("User selected RetroArch executable path: %s", chosen)
            return chosen
    except Exception as e:
        logger.error("Failed opening file dialog for RetroArch executable: %s", e)
    return None


def reset_progress_bar(
    progress_bar: Any,
    mode: str = "determinate",
    value: float = 0.0,
) -> None:
    """Reset progress bar animation state, mode, and value safely.

    Args:
        progress_bar: Progress bar widget to configure.
        mode: Progress bar mode ('determinate' or 'indeterminate').
        value: Fraction value from 0.0 to 1.0 to set when determinate.
    """
    try:
        progress_bar.stop()
        progress_bar.configure(mode=mode)
        progress_bar.set(value)
    except Exception as e:
        logger.debug("Failed resetting progress bar mode/value: %s", e)


def update_sync_progress_ui(
    progress_bar: Any,
    status_lbl: Any,
    conveyor: Any,
    pct: float,
    msg: str,
    cover_path: Optional[str] = None,
    rom_name: Optional[str] = None,
    append_log_cb: Optional[Callable[[str], None]] = None,
) -> None:
    """Update progress bar mode/value, status text, and conveyor log/covers.

    Args:
        progress_bar: CustomTkinter progress bar widget.
        status_lbl: CustomTkinter status label widget.
        conveyor: RomCoverConveyor widget.
        pct: Progress fraction from 0.0 to 1.0 (negative for indeterminate).
        msg: Status message to display.
        cover_path: Optional path to ROM cover artwork image.
        rom_name: Optional name of the ROM.
        append_log_cb: Optional callback for appending log text. Defaults to conveyor.append_log.
    """
    log_func = append_log_cb or (conveyor.append_log if hasattr(conveyor, "append_log") else None)
    is_indeterminate = pct < 0 or "calculating" in msg.lower()

    if is_indeterminate:
        try:
            if progress_bar.cget("mode") != "indeterminate":
                progress_bar.configure(mode="indeterminate")
                progress_bar.start()
        except Exception as e:
            logger.debug("Failed setting indeterminate progress mode: %s", e)
        status_lbl.configure(text=msg)
        if log_func:
            if pct < 0:
                log_func(msg)
            else:
                log_func(f"[{int(pct * 100)}%] {msg}")
    else:
        try:
            if progress_bar.cget("mode") == "indeterminate":
                progress_bar.stop()
                progress_bar.configure(mode="determinate")
            progress_bar.set(max(0.0, min(1.0, pct)))
        except Exception as e:
            logger.debug("Failed setting determinate progress mode: %s", e)
        status_lbl.configure(text=msg)
        if log_func:
            log_func(f"[{int(pct * 100)}%] {msg}")

    if rom_name and hasattr(conveyor, "add_cover"):
        conveyor.add_cover(rom_name, cover_path)


def prompt_timeout_dialog(
    parent: Any,
    progress_bar: Any,
    platform_name: str,
    backup_id: Optional[str],
    modal_cls: Any = RomMTimeoutModal,
) -> str:
    """Thread-safe invocation of RomMTimeoutModal on the UI thread.

    Args:
        parent: Parent widget providing `after()` and `winfo_toplevel()`.
        progress_bar: Progress bar to pause and switch to determinate.
        platform_name: Platform experiencing network timeout.
        backup_id: Optional pre-sync Steam backup identifier.
        modal_cls: Class or factory for RomMTimeoutModal (allows test mocks).

    Returns:
        User's selected resolution choice string ('retry', 'cancel', or 'rollback').
    """
    logger.warning(
        "RomM API timeout for platform '%s'; displaying timeout modal.",
        platform_name,
    )
    result_container = {"choice": "cancel"}
    done_event = threading.Event()

    def _show_modal() -> None:
        reset_progress_bar(progress_bar, mode="determinate")

        def _handle_choice(choice: str) -> None:
            result_container["choice"] = choice
            done_event.set()

        top = parent.winfo_toplevel() if hasattr(parent, "winfo_toplevel") else parent
        modal_cls(
            top,
            platform_name=platform_name,
            backup_id=backup_id,
            on_choice=_handle_choice,
        )

    parent.after(0, _show_modal)
    done_event.wait()
    logger.info("User selected timeout resolution choice: %s", result_container["choice"])
    return result_container["choice"]
