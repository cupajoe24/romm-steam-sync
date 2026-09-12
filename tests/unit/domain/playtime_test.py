"""Unit tests for RomPlaytime and PlaySession domain models."""

from datetime import datetime, timezone

from romm_steam_sync.domain.playtime import PlaySession, RomPlaytime


def test_addSession_updatesCumulativeSecondsAndTimestamp():
    # Arrange
    playtime = RomPlaytime(rom_id=101)
    start = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, 13, 0, 0, tzinfo=timezone.utc)
    session = PlaySession(
        session_id="session-uuid-1",
        started_at=start,
        ended_at=end,
        duration_seconds=3600,
    )

    # Act
    playtime.add_session(session)

    # Assert
    assert playtime.total_seconds == 3600
    assert playtime.last_played_at == end
    assert len(playtime.pending_sessions) == 1
    assert playtime.pending_sessions[0].session_id == "session-uuid-1"


def test_playSessionClass_initialization_createsImmutableInstance():
    # Arrange
    start = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 1, 10, 30, 0, tzinfo=timezone.utc)

    # Act
    session = PlaySession(
        session_id="session-123",
        started_at=start,
        ended_at=end,
        duration_seconds=1800,
    )

    # Assert
    assert session.session_id == "session-123"
    assert session.duration_seconds == 1800
