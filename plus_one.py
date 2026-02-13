"""BrainDrive +1 — Phone-in meeting assistant via Twilio.

Calls into a Zoom meeting, transcribes in real time, monitors the
transcript with Claude, and optionally speaks suggestions into the call.

Usage:
    python plus_one.py --meeting-id "123 456 7890" --topic "team-call"
    python plus_one.py --meeting-id "123 456 7890" --listen-only
    python plus_one.py --meeting-id "123 456 7890" --verbose

Ctrl+C stops the call, exports VTT, and shuts down cleanly.
"""

import argparse
import asyncio
import signal

from pyngrok import ngrok

from config import (
    TRANSCRIPT_FILE_PATH,
    ZOOM_DIAL_IN_NUMBER,
    WS_PORT,
    MONITOR_MODEL,
)
from transcriber import DeepgramTranscriber, TranscriptionResult
from file_writer import FileWriter
from vtt_export import save_vtt
from media_stream import MediaStreamServer
from twilio_caller import start_call, end_call
from monitor import TranscriptMonitor
from monitor_config import MonitorConfig
from suggestion_formatter import format_status_bar, format_speaking
from voice_responder import VoiceResponder
from conversation import ConversationHandler


async def run_plus_one(
    meeting_id: str,
    topic: str = "meeting",
    listen_only: bool = False,
    model: str = None,
    cooldown: int = None,
    verbose: bool = False,
    passcode: str = None,
):
    """Main +1 loop: call into Zoom, transcribe, monitor, optionally speak."""

    meeting_id_digits = meeting_id.replace(" ", "").replace("-", "")

    # --- File writer ---
    writer = FileWriter(TRANSCRIPT_FILE_PATH)
    writer.start()

    # VTT buffer
    buffer: list[dict] = []

    # --- Transcription callback ---
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

    # --- Deepgram (connect later, after Twilio stream arrives) ---
    transcriber = DeepgramTranscriber(on_transcript=on_transcript, encoding="mulaw")

    # --- WebSocket server for Twilio Media Streams ---
    async def on_audio(audio_bytes: bytes):
        await transcriber.send_audio(audio_bytes)

    async def on_stream_connected():
        """Connect Deepgram only after Twilio starts sending audio."""
        await transcriber.connect()

    media_server = MediaStreamServer(on_audio=on_audio, on_connected=on_stream_connected)
    await media_server.start()

    # --- ngrok tunnel ---
    print("Starting ngrok tunnel...")
    tunnel = ngrok.connect(WS_PORT, "http")
    # Convert https:// to wss:// URL for WebSocket
    public_url = tunnel.public_url.replace("https://", "wss://").replace("http://", "wss://")
    print(f"ngrok tunnel: {public_url}")

    # --- Place the call ---
    print(f"Calling Zoom via {ZOOM_DIAL_IN_NUMBER}...")
    print(f"Meeting ID: {meeting_id_digits}")
    call_sid = start_call(meeting_id, public_url, passcode=passcode)
    print(f"Call initiated (SID: {call_sid})")

    # Wait for Twilio to connect the media stream
    print("Waiting for media stream connection...")
    try:
        await media_server.wait_for_connection(timeout=90)
        print("Connected! +1 is in the meeting.")
    except TimeoutError:
        print("ERROR: Media stream connection timed out. Check Twilio logs.")
        await _cleanup(media_server, transcriber, writer, call_sid, tunnel)
        return

    # --- Voice + Conversation + Monitor ---
    monitor = None
    voice = None
    monitor_task = None
    conversation = None
    conversation_task = None

    if not listen_only:
        # Voice responder
        voice = VoiceResponder(media_server)

        async def on_speak(text: str):
            print(format_speaking(text))
            await voice.speak(text)

        # Conversational handler (wake-word triggered Q&A)
        conversation = ConversationHandler(
            on_speak=on_speak,
            transcript_path=str(TRANSCRIPT_FILE_PATH),
            verbose=verbose,
        )
        conversation_task = asyncio.create_task(conversation.start())

        # Proactive monitor (optional, requires Anthropic key)
        config = MonitorConfig(
            model=model or MONITOR_MODEL,
            cooldown_seconds=cooldown or MonitorConfig.cooldown_seconds,
            verbose=verbose,
        )
        try:
            config.validate()
            monitor = TranscriptMonitor(config, on_speak=on_speak)
            monitor_task = asyncio.create_task(monitor.start())
        except ValueError as e:
            print(f"Proactive monitor disabled: {e}")

    # --- Status display ---
    line_count = 0
    status = "Connected"
    model_display = model or MONITOR_MODEL
    print(format_status_bar(topic, ZOOM_DIAL_IN_NUMBER, meeting_id_digits,
                            status, model_display, line_count))
    print(f"\nListening... Transcript: {writer.path}")
    print("Press Ctrl+C to stop.\n")

    # --- Graceful shutdown ---
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    # --- Main loop: just wait for stop ---
    try:
        while not stop_event.is_set():
            await asyncio.sleep(1)
            # Periodic status update
            new_count = len(buffer)
            if new_count != line_count:
                line_count = new_count
                if verbose:
                    print(f"  [{line_count} lines transcribed]")
    except asyncio.CancelledError:
        pass

    # --- Shutdown ---
    print("\nStopping +1...")

    if conversation:
        conversation.stop()
    if conversation_task:
        conversation_task.cancel()
        try:
            await conversation_task
        except asyncio.CancelledError:
            pass

    if monitor:
        monitor.stop()
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

    await _cleanup(media_server, transcriber, writer, call_sid, tunnel)

    # Export VTT
    if buffer:
        vtt_path = save_vtt(buffer, topic=topic)
        print(f"VTT saved: {vtt_path}")
        print(f"\nTo process transcript in Claude Code:")
        print(f"  /transcript {vtt_path}")
    else:
        print("No transcript entries to export.")

    print("Done.")


async def _cleanup(media_server, transcriber, writer, call_sid, tunnel):
    """Clean up all resources."""
    try:
        end_call(call_sid)
        print("Call ended.")
    except Exception as e:
        print(f"Error ending call: {e}")

    await media_server.close()
    await transcriber.close()
    writer.close()

    try:
        ngrok.disconnect(tunnel.public_url)
        ngrok.kill()
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="BrainDrive +1 — Phone-in meeting assistant"
    )
    parser.add_argument(
        "--meeting-id", required=True,
        help='Zoom meeting ID (e.g., "123 456 7890")',
    )
    parser.add_argument(
        "--topic", default="meeting",
        help="Meeting topic (used in VTT filename and status bar)",
    )
    parser.add_argument(
        "--listen-only", action="store_true",
        help="Disable monitor and voice — transcription only",
    )
    parser.add_argument(
        "--model", default=None,
        help=f"Claude model for monitor (default: {MONITOR_MODEL})",
    )
    parser.add_argument(
        "--cooldown", type=int, default=None,
        help="Seconds between monitor analyses (default: 45)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show token usage, analysis timing, etc.",
    )
    parser.add_argument(
        "--passcode", default=None,
        help="Zoom meeting passcode (if required)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_plus_one(
            meeting_id=args.meeting_id,
            topic=args.topic,
            listen_only=args.listen_only,
            model=args.model,
            cooldown=args.cooldown,
            verbose=args.verbose,
            passcode=args.passcode,
        ))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
