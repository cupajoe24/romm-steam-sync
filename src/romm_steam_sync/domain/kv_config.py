"""Key-value configuration domain entity."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class KvConfig:
    """Key-value configuration pair persisted in the local SQLite database.

    Attributes:
        key: Unique configuration key name.
        value: Serialized configuration value string.
        updated_at: ISO 8601 timestamp string of last modification.
    """

    key: str
    value: str
    updated_at: Optional[str] = None
