"""Terminal output — color-coded suggestions from the monitor."""

from datetime import datetime


# ANSI color codes
COLORS = {
    "RELATED":  "\033[36m",   # Cyan
    "CONTEXT":  "\033[34m",   # Blue
    "CONFLICT": "\033[31m",   # Red
    "QUESTION": "\033[33m",   # Yellow
    "IDEA":     "\033[35m",   # Magenta
    "TASK":     "\033[32m",   # Green
    "EDIT":     "\033[37m",   # White
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
SEPARATOR = "\u2501" * 60  # ━ box drawing


def format_suggestion(category: str, summary: str, detail: str = "", source: str = "") -> str:
    """Format a single suggestion for terminal display.

    Args:
        category: One of RELATED, CONTEXT, CONFLICT, QUESTION, IDEA, TASK, EDIT.
        summary: One-line summary.
        detail: Optional multi-line explanation.
        source: Optional source reference (file path, decision ID, etc.).
    """
    color = COLORS.get(category, "")
    now = datetime.now().strftime("%H:%M:%S")

    lines = [SEPARATOR]
    lines.append(f"  {DIM}[{now}]{RESET} {color}{BOLD}{category}{RESET}: {summary}")
    if detail:
        for line in detail.strip().split("\n"):
            lines.append(f"  {line}")
    if source:
        lines.append(f"  {DIM}Source: {source}{RESET}")
    lines.append(SEPARATOR)
    return "\n".join(lines)


def format_speaking(text: str) -> str:
    """Format a notice that +1 is speaking in the meeting."""
    now = datetime.now().strftime("%H:%M:%S")
    return (
        f"\n{SEPARATOR}\n"
        f"  {DIM}[{now}]{RESET} {BOLD}\U0001f50a SPEAKING{RESET}: \"{text}\"\n"
        f"{SEPARATOR}"
    )


def format_status_bar(topic: str, dial_in: str, meeting_id: str,
                       status: str, model: str, line_count: int) -> str:
    """Format the top status bar for the terminal."""
    top = f"  BrainDrive +1  |  In meeting: {topic}"
    mid = f"  Zoom: {dial_in} #{meeting_id}  |  Status: {status}"
    bot = f"  Model: {model}  |  Transcript: {line_count} lines"
    width = max(len(top), len(mid), len(bot)) + 4
    border = "\u2550" * width
    return (
        f"\u2554{border}\u2557\n"
        f"\u2551{top:<{width}}\u2551\n"
        f"\u2551{mid:<{width}}\u2551\n"
        f"\u2551{bot:<{width}}\u2551\n"
        f"\u255a{border}\u255d"
    )
