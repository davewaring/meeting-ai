"""Proactive transcript monitor — periodic Claude API analysis."""

import asyncio
import os
import re
import time

import anthropic

from monitor_config import MonitorConfig
from library_context import build_full_context
from suggestion_formatter import format_suggestion

SYSTEM_PROMPT = """You are BrainDrive +1, a meeting assistant for the BrainDrive team.
You listen to meeting transcripts in real time and surface helpful context from the BrainDrive Library.

Your role:
- Surface relevant past decisions, specs, and context when the discussion touches on them
- Flag potential conflicts with existing decisions
- Note important questions, ideas, or tasks that come up
- Be concise — meeting participants have limited attention

You have access to the BrainDrive Library context below. Use it to inform your suggestions.

IMPORTANT: Only surface things that are genuinely helpful. If nothing stands out, respond with just "NONE".

When you have suggestions, format each one as:
CATEGORY: One-line summary
Detail explaining why this is relevant.
Source: file/path or decision ID

Categories: RELATED, CONTEXT, CONFLICT, QUESTION, IDEA, TASK, EDIT

Separate multiple suggestions with a blank line. Keep each suggestion to 2-3 lines max.

=== LIBRARY CONTEXT ===
{library_context}
"""

ANALYSIS_PROMPT = """Review the latest meeting transcript below. Surface any relevant context, conflicts, or suggestions based on the Library context in your system prompt.

If nothing noteworthy, respond with just "NONE".

=== TRANSCRIPT ===
{transcript}
"""


class TranscriptMonitor:
    """Watches transcript-live.txt and periodically sends it to Claude for analysis."""

    def __init__(self, config: MonitorConfig, on_suggestion: callable = None,
                 on_speak: callable = None):
        """
        Args:
            config: Monitor configuration.
            on_suggestion: callback(category, summary, detail, source) for each suggestion.
            on_speak: async callback(text) to speak a suggestion into the call.
        """
        self.config = config
        self.on_suggestion = on_suggestion
        self.on_speak = on_speak
        self._client = anthropic.Anthropic(api_key=config.api_key)
        self._last_line_count = 0
        self._last_analysis_time = 0
        self._last_file_size = 0
        self._running = False
        self._prior_suggestions: list[str] = []

    async def start(self):
        """Start the monitoring loop."""
        self.config.validate()
        self._running = True
        print(f"Monitor started (model={self.config.model}, cooldown={self.config.cooldown_seconds}s)")
        while self._running:
            await asyncio.sleep(self.config.poll_interval)
            await self._check_transcript()

    def stop(self):
        """Stop the monitoring loop."""
        self._running = False

    async def _check_transcript(self):
        """Check if transcript has grown enough to warrant analysis."""
        path = self.config.transcript_path
        try:
            stat = os.stat(path)
        except FileNotFoundError:
            return

        # Quick size check before reading
        if stat.st_size == self._last_file_size:
            return
        self._last_file_size = stat.st_size

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.strip().split("\n")
        current_count = len(lines)
        new_lines = current_count - self._last_line_count

        # Check cooldown and minimum new lines
        elapsed = time.time() - self._last_analysis_time
        if elapsed < self.config.cooldown_seconds:
            return
        if new_lines < self.config.min_new_lines:
            return

        # Run analysis
        self._last_line_count = current_count
        self._last_analysis_time = time.time()

        if self.config.verbose:
            print(f"  [monitor] Analyzing ({current_count} lines, {new_lines} new)...")

        await self._analyze(content)

    async def _analyze(self, transcript: str):
        """Send transcript to Claude API for analysis."""
        library_context = build_full_context(self.config.library_path, transcript)
        system = SYSTEM_PROMPT.format(library_context=library_context)
        user_msg = ANALYSIS_PROMPT.format(transcript=transcript)

        # Include prior suggestions to reduce redundancy
        if self._prior_suggestions:
            user_msg += "\n\n=== ALREADY SURFACED ===\n" + "\n".join(self._prior_suggestions[-10:])

        try:
            response = self._client.messages.create(
                model=self.config.model,
                max_tokens=1024,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_msg}],
            )
            text = response.content[0].text.strip()

            if self.config.verbose:
                usage = response.usage
                print(f"  [monitor] Tokens: in={usage.input_tokens} out={usage.output_tokens}")

            if text.upper() == "NONE":
                return

            self._process_response(text)

        except anthropic.APIError as e:
            print(f"  [monitor] API error: {e}")

    def _process_response(self, text: str):
        """Parse and display suggestions from the API response."""
        # Split on blank lines to separate suggestions
        blocks = re.split(r"\n\s*\n", text.strip())

        for block in blocks:
            block = block.strip()
            if not block or block.upper() == "NONE":
                continue

            lines = block.split("\n")
            first = lines[0]

            # Parse "CATEGORY: summary"
            match = re.match(r"^(RELATED|CONTEXT|CONFLICT|QUESTION|IDEA|TASK|EDIT):\s*(.+)", first)
            if not match:
                continue

            category = match.group(1)
            summary = match.group(2)

            detail = ""
            source = ""
            for line in lines[1:]:
                if line.strip().startswith("Source:"):
                    source = line.strip().removeprefix("Source:").strip()
                else:
                    detail += line + "\n"

            # Track for dedup
            self._prior_suggestions.append(f"{category}: {summary}")

            # Display
            formatted = format_suggestion(category, summary, detail.strip(), source)
            print(formatted)

            if self.on_suggestion:
                self.on_suggestion(category, summary, detail.strip(), source)

            # Speak high-priority items
            if self.on_speak and category in ("CONFLICT", "RELATED"):
                speak_text = summary
                asyncio.create_task(self.on_speak(speak_text))
