"""Process supervisor for launching RetroArch, focusing, and exit monitoring."""

from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from romm_steam_sync.adapters.retroarch_launcher import (
    RetroArchLauncher,
    bring_process_window_to_foreground,
    is_retroarch_running,
)

logger = logging.getLogger(__name__)

# Expected normal exit codes and termination signals (0 = clean, 141 = SIGPIPE, 143 = SIGTERM, 130 = SIGINT)
NORMAL_EXIT_CODES = (0, 141, -13, 143, -15, 130, -2)

BENIGN_STDERR_PREFIXES = (
    "[S_API",
    "[mist]",
    "ALSA lib",
    "pulse",
    "jack",
    "ERROR: ld.so:",
)


class GameProcessSupervisor:
    """Manages RetroArch game execution, OS window focus, and process monitoring."""

    def __init__(self) -> None:
        """Initialize GameProcessSupervisor."""
        pass

    def launch_game(
        self,
        rom_path: str,
        platform_slug: str,
        configured_retroarch_path: str,
        custom_mappings: Optional[Dict[str, str]] = None,
    ) -> Tuple[bool, str, Any]:
        """Launch the game with RetroArch.

        Args:
            rom_path: Absolute path to the local ROM file.
            platform_slug: Platform identifier.
            configured_retroarch_path: Custom RetroArch path if configured.
            custom_mappings: Custom platform to core mappings.

        Returns:
            Tuple of (success, message, process_object).
        """
        return RetroArchLauncher.launch_game(
            rom_path=rom_path,
            platform_slug=platform_slug,
            configured_retroarch_path=configured_retroarch_path,
            custom_mappings=custom_mappings,
        )

    def spawn_focus_worker(self, pid: int) -> threading.Thread:
        """Spawn background thread to bring game process window to foreground.

        Args:
            pid: Process ID of the spawned emulator.

        Returns:
            Started background thread.
        """
        def focus_worker():
            time.sleep(0.5)
            bring_process_window_to_foreground(pid)

        t = threading.Thread(target=focus_worker, daemon=True)
        t.start()
        return t

    def monitor_process(
        self,
        proc: Any,
        save_target: Optional[Path],
        session_start_mono: Optional[float],
        session_start_time: Optional[datetime],
        on_error: Callable[[int, List[str]], None],
        on_exit: Callable[[Optional[Path]], None],
    ) -> None:
        """Wait for emulator process to exit and evaluate health.

        Args:
            proc: Subprocess object.
            save_target: Save target path passed along on clean exit.
            session_start_mono: Monotonic start timestamp.
            session_start_time: Datetime start timestamp.
            on_error: Callback invoked when process aborts with an error.
            on_exit: Callback invoked on successful session completion.
        """
        try:
            logger.info(
                "Waiting for RetroArch subprocess PID %s to exit...",
                getattr(proc, "pid", "unknown"),
            )
            proc.wait()
            ret = getattr(proc, "returncode", 0)
            captured = getattr(proc, "_captured_stderr", [])
            if ret in NORMAL_EXIT_CODES:
                logger.info("RetroArch subprocess exited cleanly with return code %s", ret)
            else:
                logger.warning("RetroArch process exited with non-zero failure code %s", ret)
                if captured:
                    logger.warning("RetroArch stderr output:\n%s", "\n".join(captured[-10:]))
        except Exception as e:
            logger.warning("Error waiting for RetroArch subprocess exit: %s", e)

        # Process liveness check: if spawned wrapper returned but RetroArch is active on host
        is_running = False
        for _ in range(6):
            if is_retroarch_running():
                is_running = True
                break
            time.sleep(0.5)

        if is_running:
            logger.info("RetroArch process is running on host. Monitoring active process...")
            while is_retroarch_running():
                time.sleep(1.0)
            logger.info("Active RetroArch process has terminated.")
            on_exit(save_target)
            return

        # Check elapsed execution time to detect early crash / launch abort
        elapsed = 0.0
        if session_start_mono is not None:
            elapsed = max(0.0, time.monotonic() - session_start_mono)
        elif session_start_time:
            now_local = datetime.now()
            now_utc = datetime.now(timezone.utc)
            start_naive = session_start_time.replace(tzinfo=None)
            diff_local = abs((now_local - start_naive).total_seconds())
            diff_utc = abs((now_utc.replace(tzinfo=None) - start_naive).total_seconds())
            elapsed = min(diff_local, diff_utc)

        ret = getattr(proc, "returncode", 0)
        captured = getattr(proc, "_captured_stderr", [])
        if ret not in NORMAL_EXIT_CODES and elapsed < 5.0:
            on_error(ret, captured)
        else:
            on_exit(save_target)

    @staticmethod
    def filter_stderr_lines(stderr_lines: List[str]) -> List[str]:
        """Filter out benign driver or audio warnings from stderr output.

        Args:
            stderr_lines: Raw stderr output lines.

        Returns:
            Filtered lines containing relevant diagnostic details.
        """
        return [
            line.strip()
            for line in stderr_lines
            if line.strip() and not any(line.strip().startswith(prefix) for prefix in BENIGN_STDERR_PREFIXES)
        ]
