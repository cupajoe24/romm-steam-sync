"""Unit tests for SyncRun aggregate root."""

from romm_steam_sync.domain.sync_run import SyncRun


def test_startNew_createsRunningInstance():
    # Arrange & Act
    run = SyncRun.start_new()

    # Assert
    assert run.status == "RUNNING"
    assert run.run_id is not None
    assert run.completed_at is None
    assert run.synced_rom_count == 0


def test_complete_updatesStatusCountAndTimestamp():
    # Arrange
    run = SyncRun.start_new()

    # Act
    run.complete(count=42)

    # Assert
    assert run.status == "COMPLETED"
    assert run.synced_rom_count == 42
    assert run.completed_at is not None
    assert run.duration_seconds is not None
    assert run.duration_seconds >= 0.0


def test_fail_updatesStatusErrorAndTimestamp():
    # Arrange
    run = SyncRun.start_new()

    # Act
    run.fail(error="Connection timeout")

    # Assert
    assert run.status == "FAILED"
    assert run.error_message == "Connection timeout"
    assert run.completed_at is not None
    assert run.duration_seconds is not None
    assert run.duration_seconds >= 0.0


def test_syncRun_durationSeconds_measuresMonotonicDuration():
    # Arrange
    import time
    run = SyncRun.start_new()
    run._started_mono = time.monotonic() - 2.5

    # Act
    run.complete(count=10)

    # Assert
    assert run.duration_seconds is not None
    assert run.duration_seconds >= 2.4
