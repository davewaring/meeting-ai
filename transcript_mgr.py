"""Transcript buffer, WebSocket broadcast, and VTT export."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from fastapi import WebSocket
from config import TRANSCRIPTS_PATH


class TranscriptManager:
    """Manages live transcript entries, broadcasts to clients, exports VTT."""

    def __init__(self, library_path: str | None = None):
        self._entries: list[dict] = []
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        if library_path:
            self._transcripts_path = Path(library_path) / "transcripts"
        else:
            self._transcripts_path = TRANSCRIPTS_PATH

    def add_entry(self, start_ms: int, end_ms: int, text: str):
        """Add a transcript entry and broadcast to connected clients."""
        entry = {
            "start_ms": start_ms,
            "end_ms": end_ms,
            "text": text,
        }
        self._entries.append(entry)
        # Fire-and-forget broadcast
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast(entry))
        except RuntimeError:
            pass  # No event loop (e.g. in sync tests)

    def get_entries(self) -> list[dict]:
        """Return all buffered entries."""
        return list(self._entries)

    def get_full_text(self) -> str:
        """Return all transcript text joined."""
        return " ".join(e["text"] for e in self._entries)

    def clear(self):
        """Clear all entries."""
        self._entries.clear()

    def entry_count(self) -> int:
        return len(self._entries)

    # --- WebSocket client management ---

    async def register(self, ws: WebSocket):
        """Register a WebSocket client for live updates."""
        self._clients.add(ws)

    async def unregister(self, ws: WebSocket):
        """Remove a WebSocket client."""
        self._clients.discard(ws)

    async def _broadcast(self, entry: dict):
        """Send a new entry to all connected clients."""
        if not self._clients:
            return
        message = json.dumps({"type": "transcript", "entry": entry})
        stale = set()
        for ws in self._clients:
            try:
                await ws.send_text(message)
            except Exception:
                stale.add(ws)
        self._clients -= stale

    # --- VTT export ---

    def export_vtt(self) -> str:
        """Export buffered entries as a WebVTT string."""
        lines = ["WEBVTT", ""]
        for i, entry in enumerate(self._entries, 1):
            start = _ms_to_vtt_time(entry["start_ms"])
            end = _ms_to_vtt_time(entry["end_ms"])
            lines.append(str(i))
            lines.append(f"{start} --> {end}")
            lines.append(entry["text"])
            lines.append("")
        return "\n".join(lines)

    def save_vtt(self, meeting_title: str = "meeting") -> str:
        """Export VTT and save to the Library transcripts folder.

        Returns the filepath of the saved VTT file.
        """
        now = datetime.now()
        month_dir = self._transcripts_path / now.strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)

        safe_title = meeting_title.replace(" ", "-").replace("/", "-")
        filename = f"{now.strftime('%Y-%m-%d')}_{safe_title}.vtt"
        filepath = month_dir / filename

        vtt_content = self.export_vtt()
        filepath.write_text(vtt_content)
        print(f"VTT saved: {filepath}")
        return str(filepath)


def _ms_to_vtt_time(ms: int) -> str:
    """Convert milliseconds to VTT timestamp format HH:MM:SS.mmm."""
    total_seconds = ms // 1000
    millis = ms % 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


async def auto_process_transcript(vtt_path: str) -> str:
    """Extract decisions, tasks, and ideas from a VTT transcript using Claude.

    Saves a markdown summary file alongside the VTT and returns its path.
    """
    from anthropic import AsyncAnthropic
    from config import ANTHROPIC_API_KEY, AI_MODEL

    vtt_file = Path(vtt_path)
    if not vtt_file.exists():
        raise FileNotFoundError(f"VTT file not found: {vtt_path}")

    vtt_content = vtt_file.read_text()

    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=AI_MODEL,
        max_tokens=2048,
        system="You extract structured information from meeting transcripts. Be concise and precise.",
        messages=[{
            "role": "user",
            "content": f"""Extract the following from this meeting transcript. Use markdown format.

## Decisions
List any decisions made (who decided what).

## Action Items
List any tasks or action items (who needs to do what, by when if mentioned).

## Key Ideas
List any notable ideas or proposals discussed.

## Summary
2-3 sentence summary of the meeting.

---

Transcript:
{vtt_content}""",
        }],
    )

    output_text = response.content[0].text
    output_path = vtt_file.with_suffix(".md")
    output_path.write_text(output_text)
    print(f"Auto-processing saved: {output_path}")
    return str(output_path)
