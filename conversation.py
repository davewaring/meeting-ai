"""Wake-word triggered conversational AI — listen for "+1", think with Claude, speak via TTS."""

import asyncio
import os
import re
import time
from pathlib import Path

import anthropic

from config import ANTHROPIC_API_KEY, LIBRARY_PATH

# Wake word patterns (case-insensitive)
WAKE_PATTERNS = [
    r"\bplus\s*one\b",
    r"\+\s*1\b",
    r"\bhey\s+plus\s*one\b",
]
_WAKE_RE = re.compile("|".join(WAKE_PATTERNS), re.IGNORECASE)

# Pre-load root AGENT.md at import time so it's always in context
def _load_agent_context() -> str:
    """Load the root AGENT.md for pre-loaded context."""
    agent_path = Path(LIBRARY_PATH) / "AGENT.md"
    try:
        content = agent_path.read_text(encoding="utf-8", errors="replace")
        # Truncate to keep system prompt reasonable
        if len(content) > 6000:
            content = content[:6000] + "\n... [truncated]"
        return content
    except Exception:
        return "(Could not load AGENT.md)"

_AGENT_CONTEXT = _load_agent_context()

# Conversation model — Haiku for speed, Sonnet for depth
CONVERSATION_MODEL = "claude-haiku-4-5-20251001"

# System prompt for conversational mode
CONVERSATION_SYSTEM = """You are BrainDrive +1, a genius-level AI teammate participating in a meeting via phone.

When someone addresses you ("plus one" / "+1"), answer their question clearly and concisely.
You have tools to read files from the BrainDrive Library — use them to look up decisions, specs, build plans, tasks, and any other project documents.

Guidelines:
- Keep responses to 2-4 sentences for voice delivery. Be concise but ALWAYS give real information.
- NEVER give meta-answers like "that's the project being asked about." Always describe what something IS, its status, and key details.
- Answer from the pre-loaded context below when possible. Use tools for deeper details not in the context.
- Reference specific decisions (D##), tasks (T-###), or document sections when relevant.
- If you don't know or can't find the answer, say so honestly.
- You're speaking out loud in a meeting — be natural, not robotic.

The BrainDrive Library is at: {library_path}

## Pre-loaded Library Context (AGENT.md)

{agent_context}
"""

# Tool definitions for Claude
TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the BrainDrive Library. Use relative paths from the Library root (e.g., 'projects/active/braindrive-library/build-plan.md' or 'pulse/index.md' or 'AGENT.md').",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the BrainDrive Library root.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_files",
        "description": "Search for text across files in the BrainDrive Library. Returns matching lines with file paths. Use for finding decisions, tasks, or any content by keyword.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for (case-insensitive).",
                },
                "directory": {
                    "type": "string",
                    "description": "Subdirectory to search in (relative to Library root). Omit to search everything.",
                    "default": "",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory of the BrainDrive Library.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to Library root. Use '' or '.' for the root.",
                    "default": "",
                },
            },
            "required": [],
        },
    },
]


def has_wake_word(text: str) -> bool:
    """Check if text contains a wake word for +1."""
    return bool(_WAKE_RE.search(text))


def extract_question(text: str) -> str:
    """Extract the question/request after the wake word.

    Returns everything after the wake word match in the text.
    """
    match = _WAKE_RE.search(text)
    if not match:
        return text
    after = text[match.end():].strip()
    # Strip leading punctuation/filler
    after = re.sub(r"^[,\s]+", "", after)
    return after if after else text


def _execute_read_file(path: str) -> str:
    """Read a file from the Library."""
    full = Path(LIBRARY_PATH) / path
    try:
        if not full.exists():
            return f"File not found: {path}"
        if full.is_dir():
            return f"{path} is a directory, not a file. Use list_directory instead."
        content = full.read_text(encoding="utf-8", errors="replace")
        # Cap at 8000 chars to keep context manageable
        if len(content) > 8000:
            content = content[:8000] + f"\n\n... [truncated at 8000 chars, file is {len(content)} chars total]"
        return content
    except Exception as e:
        return f"Error reading {path}: {e}"


def _execute_search_files(query: str, directory: str = "") -> str:
    """Search for text in Library files."""
    import subprocess

    search_dir = Path(LIBRARY_PATH) / directory if directory else Path(LIBRARY_PATH)
    if not search_dir.exists():
        return f"Directory not found: {directory}"

    try:
        result = subprocess.run(
            ["grep", "-r", "-i", "-n", "--include=*.md", "-l", query, str(search_dir)],
            capture_output=True, text=True, timeout=5,
        )
        if not result.stdout.strip():
            return f"No matches found for '{query}'"

        # Get matching files, then show context for each
        files = result.stdout.strip().split("\n")[:10]  # Max 10 files
        output_parts = []
        lib_str = str(Path(LIBRARY_PATH))
        for f in files:
            rel = f.replace(lib_str + "/", "")
            # Get matching lines with context
            lines_result = subprocess.run(
                ["grep", "-i", "-n", "-m", "3", query, f],
                capture_output=True, text=True, timeout=3,
            )
            matches = lines_result.stdout.strip()
            output_parts.append(f"--- {rel} ---\n{matches}")

        return "\n\n".join(output_parts)
    except subprocess.TimeoutExpired:
        return f"Search timed out for '{query}'"
    except Exception as e:
        return f"Search error: {e}"


def _execute_list_directory(path: str = "") -> str:
    """List contents of a Library directory."""
    target = Path(LIBRARY_PATH) / path if path else Path(LIBRARY_PATH)
    if not target.exists():
        return f"Directory not found: {path}"
    if not target.is_dir():
        return f"{path} is a file, not a directory. Use read_file instead."

    entries = []
    for item in sorted(target.iterdir()):
        if item.name.startswith("."):
            continue
        suffix = "/" if item.is_dir() else ""
        entries.append(f"  {item.name}{suffix}")

    return "\n".join(entries) if entries else "(empty directory)"


def _execute_tool(name: str, input_data: dict) -> str:
    """Execute a tool call and return the result."""
    if name == "read_file":
        return _execute_read_file(input_data["path"])
    elif name == "search_files":
        return _execute_search_files(input_data["query"], input_data.get("directory", ""))
    elif name == "list_directory":
        return _execute_list_directory(input_data.get("path", ""))
    else:
        return f"Unknown tool: {name}"


class ConversationHandler:
    """Handles wake-word triggered conversations with +1.

    Watches transcript lines for wake words, collects the question,
    sends to Claude with tool use for Library access, and speaks the response.
    """

    def __init__(self, on_speak: callable, transcript_path: str, verbose: bool = False):
        """
        Args:
            on_speak: async callback(text) to speak a response into the call.
            transcript_path: Path to transcript-live.txt.
            verbose: Print debug info.
        """
        self.on_speak = on_speak
        self.transcript_path = transcript_path
        self.verbose = verbose
        self._client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self._last_line_count = 0
        self._running = False
        self._processing = False  # True while generating a response
        self._collecting = False  # True while collecting a question
        self._collected_lines: list[str] = []
        self._collect_speaker: int | None = None
        self._collect_start_time: float = 0
        self._conversation_history: list[dict] = []
        # Max 5 exchanges to keep context manageable
        self._max_history = 10

    async def start(self):
        """Start watching the transcript for wake words."""
        self._running = True
        print("[conversation] Listening for wake words ('plus one', '+1')...")
        while self._running:
            await asyncio.sleep(0.5)
            await self._check_transcript()

    def stop(self):
        self._running = False

    async def _check_transcript(self):
        """Check for new transcript lines and process them."""
        try:
            with open(self.transcript_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return

        if len(lines) <= self._last_line_count:
            # If we're collecting and no new lines for 1.5 seconds, process
            if self._collecting and (time.time() - self._collect_start_time > 1.5):
                await self._process_collected()
            return

        new_lines = lines[self._last_line_count:]
        self._last_line_count = len(lines)

        for line in new_lines:
            line = line.strip()
            if not line:
                continue

            # Parse speaker from transcript format: [HH:MM:SS] Speaker N: text
            speaker = None
            text = line
            speaker_match = re.match(r"\[\d+:\d+:\d+\]\s+Speaker\s+(\d+):\s*(.*)", line)
            if speaker_match:
                speaker = int(speaker_match.group(1))
                text = speaker_match.group(2)

            if self._processing:
                # Already generating a response, ignore new wake words
                continue

            if self._collecting:
                # We're collecting a question — add lines from the same speaker
                if speaker == self._collect_speaker or speaker is None:
                    self._collected_lines.append(text)
                    self._collect_start_time = time.time()
                else:
                    # Different speaker started talking — process what we have
                    await self._process_collected()
                continue

            # Check for wake word
            if has_wake_word(text):
                question_part = extract_question(text)
                self._collecting = True
                self._collect_speaker = speaker
                self._collected_lines = [question_part] if question_part else []
                self._collect_start_time = time.time()
                if self.verbose:
                    print(f"[conversation] Wake word detected from Speaker {speaker}")

    async def _process_collected(self):
        """Process the collected question."""
        self._collecting = False
        question = " ".join(self._collected_lines).strip()
        self._collected_lines = []

        if not question or len(question) < 3:
            return

        self._processing = True
        try:
            print(f"[conversation] Question: \"{question}\"")

            # Get full transcript for context
            try:
                with open(self.transcript_path, "r", encoding="utf-8") as f:
                    transcript = f.read()
            except FileNotFoundError:
                transcript = ""

            response_text = await self._ask_claude(question, transcript)
            if response_text:
                print(f"[conversation] Response: \"{response_text}\"")
                await self.on_speak(response_text)
        except Exception as e:
            print(f"[conversation] Error: {e}")
        finally:
            self._processing = False

    async def _ask_claude(self, question: str, transcript: str) -> str | None:
        """Send the question to Claude with tool use and return the text response."""
        system = CONVERSATION_SYSTEM.format(
            library_path=str(LIBRARY_PATH),
            agent_context=_AGENT_CONTEXT,
        )

        # Build user message with transcript context + question
        user_content = f"Here is the current meeting transcript:\n\n{transcript}\n\n---\n\nSomeone just asked you: \"{question}\"\n\nAnswer their question. Use tools to look up any files you need."

        # Add to conversation history
        self._conversation_history.append({"role": "user", "content": user_content})

        # Keep history bounded
        if len(self._conversation_history) > self._max_history:
            self._conversation_history = self._conversation_history[-self._max_history:]

        messages = list(self._conversation_history)

        # Tool use loop — Claude may call tools multiple times
        max_iterations = 5
        for i in range(max_iterations):
            try:
                response = self._client.messages.create(
                    model=CONVERSATION_MODEL,
                    max_tokens=400,
                    system=system,
                    tools=TOOLS,
                    messages=messages,
                )
            except anthropic.APIError as e:
                print(f"[conversation] API error: {e}")
                return None

            if self.verbose:
                usage = response.usage
                print(f"[conversation] Tokens: in={usage.input_tokens} out={usage.output_tokens}")

            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                # Process all tool calls
                tool_results = []
                assistant_content = response.content
                for block in response.content:
                    if block.type == "tool_use":
                        if self.verbose:
                            print(f"[conversation] Tool: {block.name}({block.input})")
                        result = _execute_tool(block.name, block.input)
                        if self.verbose:
                            preview = result[:200] + "..." if len(result) > 200 else result
                            print(f"[conversation] Result: {preview}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add assistant message and tool results to continue the loop
                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})
                continue

            # Got a final text response
            text_parts = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_parts.append(block.text)
            final_text = " ".join(text_parts).strip()

            # Save to history
            self._conversation_history.append({"role": "assistant", "content": final_text})

            return final_text

        return "Sorry, I got stuck looking things up. Could you ask again?"
