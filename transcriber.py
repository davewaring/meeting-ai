"""Streaming transcription via Deepgram SDK v5."""

import asyncio
from typing import Callable
from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from collections import Counter
from config import DEEPGRAM_API_KEY, SAMPLE_RATE, ENABLE_DIARIZATION


def _dominant_speaker(words) -> int | None:
    """Return the most common speaker ID from word-level diarization data.

    Args:
        words: list of word objects with a ``speaker`` attribute (from Deepgram).
    Returns:
        The majority speaker ID, or None if no speaker data is present.
    """
    speakers = [w.speaker for w in words if hasattr(w, "speaker") and w.speaker is not None]
    if not speakers:
        return None
    return Counter(speakers).most_common(1)[0][0]


class TranscriptionResult:
    """A single transcription result from Deepgram."""

    def __init__(self, text: str, start: float, end: float, is_final: bool, speaker: int | None = None):
        self.text = text
        self.start = start  # seconds
        self.end = end  # seconds
        self.is_final = is_final
        self.speaker = speaker

    def __repr__(self):
        kind = "FINAL" if self.is_final else "interim"
        spk = f" S{self.speaker}" if self.speaker is not None else ""
        return f"[{self.start:.1f}-{self.end:.1f}] ({kind}{spk}) {self.text}"


class DeepgramTranscriber:
    """Manages a streaming connection to Deepgram using SDK v5."""

    def __init__(self, on_transcript: Callable | None = None):
        """
        Args:
            on_transcript: callback(TranscriptionResult) called for each result
        """
        self.on_transcript = on_transcript
        self._client = AsyncDeepgramClient(api_key=DEEPGRAM_API_KEY)
        self._socket = None
        self._ctx_manager = None
        self._recv_task = None

    async def connect(self):
        """Open a streaming WebSocket connection to Deepgram."""
        params = dict(
            model="nova-3",
            language="en",
            encoding="linear16",
            sample_rate=str(SAMPLE_RATE),
            channels="1",
            punctuate="true",
            interim_results="true",
            utterance_end_ms="1000",
            vad_events="true",
            endpointing="300",
        )
        if ENABLE_DIARIZATION:
            params["diarize"] = "true"
        self._ctx_manager = self._client.listen.v1.connect(**params)
        self._socket = await self._ctx_manager.__aenter__()
        # Start background task to receive transcription results
        self._recv_task = asyncio.create_task(self._receive_loop())
        print("Deepgram connected and ready.")

    async def _receive_loop(self):
        """Background task that reads results from Deepgram."""
        try:
            while self._socket:
                try:
                    result = await self._socket.recv()
                    if result is None:
                        break
                    await self._handle_result(result)
                except Exception as e:
                    if "closed" in str(e).lower():
                        break
                    print(f"Deepgram recv error: {e}")
                    break
        except asyncio.CancelledError:
            pass

    async def _handle_result(self, result):
        """Process a transcription result event."""
        # Check if it's a results event (has channel attribute)
        if not hasattr(result, "channel") or result.channel is None:
            return

        try:
            channel = result.channel
            if not hasattr(channel, "alternatives"):
                return
            alternatives = channel.alternatives
            if not alternatives:
                return
            text = alternatives[0].transcript.strip()
            if not text:
                return

            speaker = None
            if ENABLE_DIARIZATION:
                words = getattr(alternatives[0], "words", None)
                if words:
                    speaker = _dominant_speaker(words)

            tr = TranscriptionResult(
                text=text,
                start=result.start,
                end=result.start + result.duration,
                is_final=result.is_final,
                speaker=speaker,
            )

            if self.on_transcript:
                if asyncio.iscoroutinefunction(self.on_transcript):
                    await self.on_transcript(tr)
                else:
                    self.on_transcript(tr)
        except (IndexError, AttributeError) as e:
            print(f"Error parsing transcript: {e}")

    async def send_audio(self, audio_bytes: bytes):
        """Send an audio chunk to Deepgram."""
        if self._socket:
            await self._socket.send_media(audio_bytes)

    async def close(self):
        """Close the Deepgram connection."""
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self._ctx_manager:
            await self._ctx_manager.__aexit__(None, None, None)
            self._ctx_manager = None
            self._socket = None
        print("Deepgram connection closed.")


async def create_deepgram_connection(on_transcript=None) -> DeepgramTranscriber:
    """Create and return a connected Deepgram transcriber."""
    transcriber = DeepgramTranscriber(on_transcript=on_transcript)
    await transcriber.connect()
    return transcriber


async def transcribe_audio_file(filepath: str) -> str | None:
    """Transcribe an audio file via Deepgram (batch, not streaming).

    Used for testing. Returns the full transcript text.
    """
    import os
    if not os.path.exists(filepath):
        return None

    client = AsyncDeepgramClient(api_key=DEEPGRAM_API_KEY)

    with open(filepath, "rb") as f:
        audio_data = f.read()

    response = await client.listen.v1.media.transcribe_file(
        request=audio_data,
        model="nova-3",
        language="en",
        punctuate=True,
    )

    return response.results.channels[0].alternatives[0].transcript


async def _demo():
    """Demo: capture from BlackHole and transcribe in real-time."""
    from audio_capture import start_capture_stream

    def on_result(result: TranscriptionResult):
        if result.is_final:
            print(f"  >> {result.text}")
        else:
            print(f"     {result.text}", end="\r")

    transcriber = await create_deepgram_connection(on_transcript=on_result)

    stop_event = asyncio.Event()

    async def send_to_deepgram(audio_bytes: bytes):
        await transcriber.send_audio(audio_bytes)

    print("Transcribing... Press Ctrl+C to stop.\n")
    try:
        await start_capture_stream(send_to_deepgram, stop_event)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        await transcriber.close()


if __name__ == "__main__":
    asyncio.run(_demo())
