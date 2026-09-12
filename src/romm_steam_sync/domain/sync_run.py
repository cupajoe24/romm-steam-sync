"""SyncRun aggregate root representing a library synchronization run."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import time
from typing import Optional
import uuid


@dataclass
class SyncRun:
    """Aggregate tracking the execution state and statistics of a sync run.

    Attributes:
        run_id: Unique UUID string for the sync run.
        started_at: UTC timestamp when the sync started.
        status: Execution status ('RUNNING', 'COMPLETED', 'CANCELLED', 'FAILED').
        completed_at: UTC timestamp when the sync finished.
        synced_rom_count: Number of successfully processed ROMs.
        error_message: Optional error message if the run failed.
        duration_seconds: Elapsed execution duration in seconds.
    """

    run_id: str
    started_at: datetime
    status: str = "RUNNING"  # RUNNING, COMPLETED, CANCELLED, FAILED
    completed_at: Optional[datetime] = None
    synced_rom_count: int = 0
    error_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    _started_mono: float = field(default_factory=time.monotonic, repr=False, compare=False)

    @classmethod
    def start_new(cls) -> "SyncRun":
        """Factory method to initiate a new active synchronization run.

        Returns:
            Newly created SyncRun in RUNNING state.
        """
        return cls(
            run_id=str(uuid.uuid4()),
            started_at=datetime.now(timezone.utc),
            status="RUNNING",
            _started_mono=time.monotonic(),
        )

    def complete(self, count: int) -> None:
        """Mark the sync run as successfully completed.

        Args:
            count: Total count of ROMs synchronized.
        """
        self.status = "COMPLETED"
        self.synced_rom_count = count
        self.completed_at = datetime.now(timezone.utc)
        self.duration_seconds = max(0.0, time.monotonic() - getattr(self, "_started_mono", time.monotonic()))

    def fail(self, error: str) -> None:
        """Mark the sync run as failed with an error message.

        Args:
            error: Descriptive error message explaining the failure.
        """
        self.status = "FAILED"
        self.error_message = error
        self.completed_at = datetime.now(timezone.utc)
        self.duration_seconds = max(0.0, time.monotonic() - getattr(self, "_started_mono", time.monotonic()))
