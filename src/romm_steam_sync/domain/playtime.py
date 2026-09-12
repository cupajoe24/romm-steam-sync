"""RomPlaytime aggregate root and PlaySession value object."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass(frozen=True)
class PlaySession:
    """Immutable play session value object recording gameplay duration.

    Attributes:
        session_id: Unique UUID string for this play session.
        started_at: UTC datetime when the game was launched.
        ended_at: UTC datetime when the game process exited.
        duration_seconds: Elapsed gameplay time in seconds.
    """

    session_id: str
    started_at: datetime
    ended_at: datetime
    duration_seconds: int


@dataclass
class RomPlaytime:
    """Aggregate tracking accumulated playtime and pending sessions for a ROM.

    Attributes:
        rom_id: RomM identifier of the ROM.
        total_seconds: Cumulative play duration in seconds.
        last_played_at: UTC timestamp when game was last closed.
        pending_sessions: List of un-synced PlaySession instances.
    """

    rom_id: int
    total_seconds: int = 0
    last_played_at: Optional[datetime] = None
    pending_sessions: List[PlaySession] = field(default_factory=list)

    def add_session(self, session: PlaySession) -> None:
        """Append a completed play session and update cumulative statistics.

        Args:
            session: PlaySession instance to record.
        """
        self.pending_sessions.append(session)
        self.total_seconds += session.duration_seconds
        self.last_played_at = session.ended_at
