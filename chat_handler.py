"""AI chat handler — Claude API, intent detection, action notes."""

import re
from anthropic import AsyncAnthropic
from config import ANTHROPIC_API_KEY, AI_MODEL

_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

SYSTEM_PROMPT = """You are a helpful AI assistant participating in a live meeting. You have access to:
1. The live transcript of the current meeting
2. Relevant content from the BrainDrive Library (a knowledge base of project docs, decisions, and specs)

Be concise — the user is in a meeting and needs quick, useful answers. Reference specific details from the transcript or Library when relevant. If you don't have enough context, say so briefly."""

NOTE_PATTERNS = [
    r"^make a note\b",
    r"^note[:\s]",
    r"^capture\b",
    r"^remind\b",
    r"^remember\b",
    r"^action item[:\s]",
    r"^todo[:\s]",
]


def detect_intent(message: str) -> str:
    """Classify a message as 'note' or 'question'."""
    lower = message.strip().lower()
    for pattern in NOTE_PATTERNS:
        if re.match(pattern, lower):
            return "note"
    return "question"


async def handle_chat_message(
    message: str,
    transcript_text: str,
    library_results: list[dict],
) -> str:
    """Handle a chat message and return the AI response."""
    if not _client:
        return "Error: ANTHROPIC_API_KEY not configured."

    # Build user prompt with context
    parts = []

    if transcript_text:
        # Truncate to last ~4000 chars to keep prompt manageable
        truncated = transcript_text[-4000:] if len(transcript_text) > 4000 else transcript_text
        parts.append(f"## Meeting Transcript (recent)\n{truncated}")

    if library_results:
        lib_text = "\n\n".join(
            f"**{r['file']}:**\n{r['snippet']}" for r in library_results[:5]
        )
        parts.append(f"## Library Context\n{lib_text}")

    parts.append(f"## User Question\n{message}")

    user_content = "\n\n---\n\n".join(parts)

    response = await _client.messages.create(
        model=AI_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    return response.content[0].text


class NoteManager:
    """Captures and stores action notes with transcript context."""

    def __init__(self):
        self._notes: list[dict] = []

    def capture_note(
        self,
        message: str,
        transcript_entries: list[dict],
        timestamp_ms: int,
    ) -> dict:
        """Capture a note with surrounding transcript context.

        Args:
            message: The note text from the user
            transcript_entries: Recent transcript entries for context
            timestamp_ms: Current timestamp in the meeting
        """
        # Get last 2-3 minutes of context (entries within 180s before timestamp)
        context_window_ms = 180_000
        context = [
            e for e in transcript_entries
            if e["start_ms"] >= (timestamp_ms - context_window_ms)
        ]

        note = {
            "message": message,
            "timestamp_ms": timestamp_ms,
            "context": context,
        }
        self._notes.append(note)
        return note

    def get_notes(self) -> list[dict]:
        """Return all captured notes."""
        return list(self._notes)

    def clear(self):
        """Clear all notes."""
        self._notes.clear()
