"""Export transcript buffer as VTT file."""

from datetime import datetime
from pathlib import Path


def format_vtt(entries: list[dict]) -> str:
    """Format transcript entries as a WebVTT string.

    Each entry: {"start_ms": int, "end_ms": int, "text": str, "speaker": int | None}
    """
    lines = ["WEBVTT", ""]
    for i, entry in enumerate(entries, 1):
        start = _ms_to_vtt_time(entry["start_ms"])
        end = _ms_to_vtt_time(entry["end_ms"])
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        speaker = entry.get("speaker")
        if speaker is not None:
            lines.append(f"<v Speaker {speaker}>{entry['text']}")
        else:
            lines.append(entry["text"])
        lines.append("")
    return "\n".join(lines)


def save_vtt(entries: list[dict], topic: str = "meeting", output_dir: Path | str | None = None) -> str:
    """Export entries as VTT and save to the output directory.

    Returns the filepath of the saved VTT file.
    """
    from config import VTT_OUTPUT_DIR

    if output_dir is None:
        output_dir = VTT_OUTPUT_DIR
    output_dir = Path(output_dir)

    now = datetime.now()
    month_dir = output_dir / now.strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)

    safe_topic = topic.replace(" ", "-").replace("/", "-")
    filename = f"{now.strftime('%Y-%m-%d_%H-%M')}_{safe_topic}.vtt"
    filepath = month_dir / filename

    vtt_content = format_vtt(entries)
    filepath.write_text(vtt_content)
    return str(filepath)


def _ms_to_vtt_time(ms: int) -> str:
    """Convert milliseconds to VTT timestamp format HH:MM:SS.mmm."""
    total_seconds = ms // 1000
    millis = ms % 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
