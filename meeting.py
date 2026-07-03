"""CLI entry point for meeting transcription.

Captures audio from BlackHole + microphone and transcribes locally with
faster-whisper. Default is SPLIT-CHANNEL mode: the mic and BlackHole are
transcribed separately, so every line carries ground-truth speaker
attribution (mic = you, BlackHole = the remote side) with no diarization
model. Writes a live transcript file that Claude Code can read at any time.

Usage:
    python meeting.py [--topic NAME]           # split-channel local Whisper (default)
    python meeting.py [--topic NAME] --mixed   # legacy single-stream (no speakers)
    python meeting.py [--topic NAME] --cloud   # Deepgram cloud (implies mixed)
    python meeting.py --model large-v3         # use a larger Whisper model

Ctrl+C stops the meeting and exports a VTT file.
"""

import argparse
import asyncio
import signal
import threading
import time

from audio_capture import start_capture_stream, start_split_capture_stream
from transcriber import TranscriptionResult
from file_writer import FileWriter
from vtt_export import save_vtt
from config import (
    TRANSCRIPT_FILE_PATH,
    WHISPER_MODEL,
    MIC_SPEAKER_LABEL,
    REMOTE_SPEAKER_LABEL,
)


async def run_meeting(
    topic: str = "meeting",
    cloud: bool = False,
    model: str | None = None,
    mixed: bool = False,
):
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

    # Graceful shutdown via Ctrl+C
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    transcribers = []

    if cloud:
        # Deepgram path is single-stream; split not supported here
        from transcriber import DeepgramTranscriber
        transcriber = DeepgramTranscriber(on_transcript=on_transcript)
        await transcriber.connect()
        transcribers.append(transcriber)

        async def send_audio(audio_bytes: bytes):
            await transcriber.send_audio(audio_bytes)

        capture = start_capture_stream(send_audio, stop_event)

    elif mixed:
        # Legacy fallback: both channels mixed into one stream, no speakers
        from local_transcriber import LocalTranscriber
        whisper_model = model or WHISPER_MODEL
        transcriber = LocalTranscriber(on_transcript=on_transcript, model_size=whisper_model)
        await transcriber.connect()
        transcribers.append(transcriber)

        async def send_audio(audio_bytes: bytes):
            await transcriber.send_audio(audio_bytes)

        capture = start_capture_stream(send_audio, stop_event)

    else:
        # Default: split-channel — one transcriber per channel, shared model,
        # channel = speaker. Shared wall clock keeps both timelines aligned.
        from local_transcriber import LocalTranscriber
        whisper_model = model or WHISPER_MODEL
        transcribe_lock = threading.Lock()
        clock_zero = time.monotonic()

        remote_t = LocalTranscriber(
            on_transcript=on_transcript,
            model_size=whisper_model,
            speaker=REMOTE_SPEAKER_LABEL,
            transcribe_lock=transcribe_lock,
            clock_zero=clock_zero,
        )
        await remote_t.connect()  # loads the model once

        mic_t = LocalTranscriber(
            on_transcript=on_transcript,
            model_size=whisper_model,
            speaker=MIC_SPEAKER_LABEL,
            shared_model=remote_t.model,
            transcribe_lock=transcribe_lock,
            clock_zero=clock_zero,
        )
        await mic_t.connect()
        transcribers.extend([remote_t, mic_t])

        by_source = {"remote": remote_t, "mic": mic_t}

        async def send_split_audio(source: str, audio_bytes: bytes):
            await by_source[source].send_audio(audio_bytes)

        capture = start_split_capture_stream(send_split_audio, stop_event)
        print(f"Split-channel mode: mic → \"{MIC_SPEAKER_LABEL}\", remote → \"{REMOTE_SPEAKER_LABEL}\"")

    print(f"Meeting started. Transcript: {writer.path}")
    print("Press Ctrl+C to stop.\n")

    try:
        await capture
    except asyncio.CancelledError:
        pass

    # Shutdown
    print("\nStopping meeting...")
    for t in transcribers:
        await t.close()
    writer.close()

    # Export VTT
    if buffer:
        vtt_path = save_vtt(buffer, topic=topic)
        print(f"VTT saved: {vtt_path}")
        print(f"\nTo process transcript in Claude Code:")
        print(f"  /capture {vtt_path}")
    else:
        print("No transcript entries to export.")

    print("Done.")


def main():
    parser = argparse.ArgumentParser(description="Real-time meeting transcription")
    parser.add_argument("--topic", default="meeting", help="Meeting topic (used in VTT filename)")
    parser.add_argument("--cloud", action="store_true", help="Use Deepgram cloud instead of local Whisper (implies --mixed)")
    parser.add_argument("--mixed", action="store_true", help="Legacy fallback: mix mic + BlackHole into one stream (no speaker attribution)")
    parser.add_argument("--model", default=None, help="Whisper model size (tiny/base/small/medium/large-v3)")
    args = parser.parse_args()

    try:
        asyncio.run(run_meeting(topic=args.topic, cloud=args.cloud, model=args.model, mixed=args.mixed))
    except KeyboardInterrupt:
        pass  # Shutdown already handled by signal handler


if __name__ == "__main__":
    main()
