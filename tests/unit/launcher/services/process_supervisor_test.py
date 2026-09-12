"""Unit tests for GameProcessSupervisor service."""

from pathlib import Path
import time
from unittest.mock import MagicMock, patch

from romm_steam_sync.launcher.services.process_supervisor import (
    GameProcessSupervisor,
)


def test_launchGame_invokesRetroArchLauncher():
    # Arrange
    supervisor = GameProcessSupervisor()
    mock_proc = MagicMock()

    with patch("romm_steam_sync.launcher.services.process_supervisor.RetroArchLauncher.launch_game") as mock_launch:
        mock_launch.return_value = (True, "Launched successfully", mock_proc)

        # Act
        success, msg, proc = supervisor.launch_game(
            rom_path="/path/to/game.sfc",
            platform_slug="snes",
            configured_retroarch_path="C:/RetroArch/retroarch.exe",
        )

        # Assert
        assert success is True
        assert "Launched" in msg
        assert proc == mock_proc


def test_monitorProcess_handlesCleanExit():
    # Arrange
    supervisor = GameProcessSupervisor()
    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.returncode = 0
    mock_proc._captured_stderr = []

    on_error = MagicMock()
    on_exit = MagicMock()
    save_target = Path("/saves/game.srm")

    with patch("romm_steam_sync.launcher.services.process_supervisor.is_retroarch_running", return_value=False):
        # Act
        supervisor.monitor_process(
            proc=mock_proc,
            save_target=save_target,
            session_start_mono=time.monotonic() - 10.0,
            session_start_time=None,
            on_error=on_error,
            on_exit=on_exit,
        )

        # Assert
        on_exit.assert_called_once_with(save_target)
        on_error.assert_not_called()


def test_monitorProcess_detectsShortCrashAbort():
    # Arrange
    supervisor = GameProcessSupervisor()
    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.returncode = 1
    mock_proc._captured_stderr = ["Fatal error loading core"]

    on_error = MagicMock()
    on_exit = MagicMock()

    with patch("romm_steam_sync.launcher.services.process_supervisor.is_retroarch_running", return_value=False):
        # Act: elapsed time is only 1 second (< 5.0s abort threshold)
        supervisor.monitor_process(
            proc=mock_proc,
            save_target=None,
            session_start_mono=time.monotonic() - 1.0,
            session_start_time=None,
            on_error=on_error,
            on_exit=on_exit,
        )

        # Assert
        on_error.assert_called_once_with(1, ["Fatal error loading core"])
        on_exit.assert_not_called()


def test_monitorProcess_waitsForHostLiveness():
    # Arrange
    supervisor = GameProcessSupervisor()
    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.returncode = 0

    on_error = MagicMock()
    on_exit = MagicMock()

    # RetroArch running on host for 2 checks, then exits
    liveness_seq = [True, True, False]

    with patch("romm_steam_sync.launcher.services.process_supervisor.is_retroarch_running", side_effect=liveness_seq), \
         patch("time.sleep"):
        # Act
        supervisor.monitor_process(
            proc=mock_proc,
            save_target=None,
            session_start_mono=time.monotonic() - 20.0,
            session_start_time=None,
            on_error=on_error,
            on_exit=on_exit,
        )

        # Assert
        on_exit.assert_called_once()
        on_error.assert_not_called()


def test_filterStderrLines_stripsBenignDriverNoise():
    # Arrange
    raw_lines = [
        "[S_API FAIL] SteamAPI_Init() failed",
        "[mist] info: mist wrapper loaded",
        "ALSA lib pcm.c: unknown PCM",
        "pulse: connection failed",
        "ERROR: ld.so: object cannot be loaded",
        "Failed to load /cores/snes9x_libretro.so: file not found",
    ]

    # Act
    filtered = GameProcessSupervisor.filter_stderr_lines(raw_lines)

    # Assert
    assert len(filtered) == 1
    assert "Failed to load /cores/snes9x_libretro.so" in filtered[0]
