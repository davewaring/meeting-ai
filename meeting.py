"""CLI entry point for meeting transcription.

Captures audio from BlackHole + microphone, streams to Deepgram for
transcription, and writes a live transcript file that Claude Code can
read at any time.

Usage:
    python meeting.py [--topic NAME]

Ctrl+C stops the meeting and exports a VTT file.
"""

import argparse
import asyncio
import signal

from audio_capture import start_capture_stream
from transcriber import DeepgramTranscriber, TranscriptionResult
from file_writer import FileWriter
from vtt_export import save_vtt
from config import TRANSCRIPT_FILE_PATH


async def run_meeting(topic: str = "meeting"):
    """Main meeting loop: capture audio, transcribe, write file."""

    # Initialize file writer (overwrites previous transcript)
    writer = FileWriter(TRANSCRIPT_FILE_PATH)
    writer.start()

    # In-memory buffer for VTT export at end
    buffer: list[dict] = []

    # Transcription callback — only process final results
    async def on_transcript(result: TranscriptionResult):
        if result.is_final and result.text:
            writer.write_line(result.text, speaker=result.speaker, elapsed_seconds=result.start)
            entry = {
                "start_ms": int(result.start * 1000),
                "end_ms": int(result.end * 1000),
                "text": result.text,
            }
            if result.speaker is not None:
                entry["speaker"] = result.speaker
            buffer.append(entry)

    # Connect to Deepgram
    transcriber = DeepgramTranscriber(on_transcript=on_transcript)
    await transcriber.connect()

    # Graceful shutdown via Ctrl+C
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    # Audio capture → Deepgram pipeline
    async def send_audio(audio_bytes: bytes):
        await transcriber.send_audio(audio_bytes)

    print(f"Meeting started. Transcript: {writer.path}")
    print("Press Ctrl+C to stop.\n")

    try:
        await start_capture_stream(send_audio, stop_event)
    except asyncio.CancelledError:
        pass

    # Shutdown
    print("\nStopping meeting...")
    await transcriber.close()
    writer.close()

    # Export VTT
    if buffer:
        vtt_path = save_vtt(buffer, topic=topic)
        print(f"VTT saved: {vtt_path}")
        print(f"\nTo process transcript in Claude Code:")
        print(f"  /transcript {vtt_path}")
    else:
        print("No transcript entries to export.")

    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Real-time meeting transcription")
    parser.add_argument("--topic", default="meeting", help="Meeting topic (used in VTT filename)")
    args = parser.parse_args()

    try:
        asyncio.run(run_meeting(topic=args.topic))
    except KeyboardInterrupt:
        pass  # Shutdown already handled by signal handler


if __name__ == "__main__":
    main()
