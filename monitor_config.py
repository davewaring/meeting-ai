"""Configuration dataclass for the proactive monitor."""

from dataclasses import dataclass
from config import (
    ANTHROPIC_API_KEY,
    MONITOR_MODEL,
    MONITOR_COOLDOWN,
    MONITOR_MIN_NEW_LINES,
    LIBRARY_PATH,
    TRANSCRIPT_FILE_PATH,
)


@dataclass
class MonitorConfig:
    """Settings for the transcript monitor."""
    api_key: str = ANTHROPIC_API_KEY
    model: str = MONITOR_MODEL
    cooldown_seconds: int = MONITOR_COOLDOWN
    min_new_lines: int = MONITOR_MIN_NEW_LINES
    library_path: str = str(LIBRARY_PATH)
    transcript_path: str = str(TRANSCRIPT_FILE_PATH)
    poll_interval: float = 2.0
    verbose: bool = False

    def validate(self):
        """Raise ValueError if required fields are missing."""
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the monitor")
