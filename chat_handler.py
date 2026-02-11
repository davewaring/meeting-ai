"""AI chat handler — Claude API, intent detection, action notes."""

import re
from anthropic import AsyncAnthropic
from config import ANTHROPIC_API_KEY, AI_MODEL
from library_search import search_library

_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

MAX_TOOL_CALLS = 3

SEARCH_TOOL = {
    "name": "search_library",
    "description": (
        "Search the BrainDrive Library (project docs, specs, decisions) using keywords. "
        "Pass short keyword queries, NOT full sentences. "
        "Example: 'plugin architecture' or 'node_modules bloat'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Short keyword search query",
            },
        },
        "required": ["query"],
    },
}

SYSTEM_PROMPT = """You are a helpful AI assistant participating in a live meeting. You have access to:
1. The live transcript of the current meeting
2. A search_library tool to look up the BrainDrive Library (project docs, decisions, specs)

When the user asks about project context, decisions, specs, architecture, or anything that might be documented, use the search_library tool with short keyword queries to find relevant information. You can search multiple times with different keywords if your first search doesn't find what you need.

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
) -> str:
    """Handle a chat message using an agentic tool-use loop.

    Claude can call search_library iteratively (up to MAX_TOOL_CALLS times)
    to find relevant Library context before answering.
    """
    if not _client:
        return "Error: ANTHROPIC_API_KEY not configured."

    # Build initial user prompt with transcript context
    parts = []
    if transcript_text:
        truncated = transcript_text[-4000:] if len(transcript_text) > 4000 else transcript_text
        parts.append(f"## Meeting Transcript (recent)\n{truncated}")
    parts.append(f"## User Question\n{message}")
    user_content = "\n\n---\n\n".join(parts)

    messages = [{"role": "user", "content": user_content}]

    for _ in range(MAX_TOOL_CALLS + 1):
        response = await _client.messages.create(
            model=AI_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=[SEARCH_TOOL],
        )

        if response.stop_reason == "end_turn":
            # Extract text blocks from the response
            text_parts = [b.text for b in response.content if b.type == "text"]
            return "\n".join(text_parts) if text_parts else ""

        # Process tool calls
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                query = block.input.get("query", "")
                results = search_library(query)
                result_text = "\n\n".join(
                    f"**{r['file']}:**\n{r['snippet']}" for r in results
                ) if results else "No results found."
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text,
                })
        messages.append({"role": "user", "content": tool_results})

    # Fallback: hit max tool calls, do a final call without tools
    response = await _client.messages.create(
        model=AI_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    text_parts = [b.text for b in response.content if b.type == "text"]
    return "\n".join(text_parts) if text_parts else ""


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
