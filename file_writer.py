"""Writes live transcript to a plain text file."""

import time
from pathlib import Path


class FileWriter:
    """Appends timestamped transcript lines to a file, flushing after each write."""

    def __init__(self, file_path: Path | str):
        self._path = Path(file_path)
        self._file = None
        self._start_time: float | None = None

    def start(self):
        """Open the file (overwriting any previous content) and record start time."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "w", encoding="utf-8")
        self._start_time = time.monotonic()

    def write_line(self, text: str, speaker: int | None = None, elapsed_seconds: float | None = None):
        """Append a timestamped line and flush immediately.

        Format: [HH:MM:SS] Speaker N: text
        Or:     [HH:MM:SS] text (when no speaker)
        """
        if self._file is None:
            raise RuntimeError("FileWriter not started. Call start() first.")

        if elapsed_seconds is None:
            elapsed_seconds = time.monotonic() - self._start_time

        timestamp = _format_elapsed(elapsed_seconds)

        if speaker is not None:
            line = f"[{timestamp}] Speaker {speaker}: {text}\n"
        else:
            line = f"[{timestamp}] {text}\n"

        self._file.write(line)
        self._file.flush()

    def close(self):
        """Close the file."""
        if self._file:
            self._file.close()
            self._file = None

    @property
    def path(self) -> Path:
        return self._path


def _format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as HH:MM:SS."""
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"
