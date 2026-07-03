"""Local streaming transcription using faster-whisper.

Drop-in replacement for DeepgramTranscriber — same interface, no cloud dependency.
Uses VAD (voice activity detection) to segment speech, then transcribes complete
utterances with faster-whisper. No speaker diarization.

Requires: pip install faster-whisper
"""

import asyncio
import time
from typing import Callable

import numpy as np

from transcriber import TranscriptionResult
from config import SAMPLE_RATE

# Audio constants
BYTES_PER_SAMPLE = 2  # int16

# VAD thresholds
SILENCE_RMS_THRESHOLD = 250  # Below this RMS = silence
SILENCE_DURATION_S = 0.8  # Seconds of silence to trigger transcription
MIN_SPEECH_S = 0.5  # Minimum speech duration worth transcribing
MAX_BUFFER_S = 30  # Force transcribe if buffer exceeds this


class LocalTranscriber:
    """Local Whisper transcriber with VAD-based chunking.

    Buffers incoming audio, detects speech boundaries via energy-based VAD,
    and transcribes complete utterances using faster-whisper.
    """

    def __init__(
        self,
        on_transcript: Callable | None = None,
        model_size: str = "medium",
        speaker: str | int | None = None,
        shared_model=None,
        transcribe_lock=None,
        clock_zero: float | None = None,
    ):
        """
        Args:
            speaker: label stamped on every result from this transcriber
                     (split-channel mode: one transcriber per channel).
            shared_model: reuse an already-loaded WhisperModel (split mode
                     runs two transcribers; loading the model twice would
                     double memory for nothing).
            transcribe_lock: threading.Lock shared between instances so only
                     one Whisper call runs at a time.
            clock_zero: shared time.monotonic() session start. When set,
                     segment timestamps are wall-clock offsets from it —
                     keeping two channels' timelines aligned regardless of
                     how much audio each buffered. When None, falls back to
                     cumulative audio time (single-channel behavior).
        """
        self.on_transcript = on_transcript
        self.model_size = model_size
        self.speaker = speaker
        self.model = shared_model
        self._transcribe_lock = transcribe_lock
        self._clock_zero = clock_zero
        self._buffer_wall_start: float | None = None
        self._audio_buffer = bytearray()
        self._lock = asyncio.Lock()
        self._running = False
        self._elapsed_seconds = 0.0  # Total audio time processed
        self._silence_start: float | None = None
        self._has_speech = False
        self._process_task = None

    async def connect(self):
        """Load the Whisper model (may take a few seconds on first run)."""
        if self.model is None:
            loop = asyncio.get_event_loop()
            print(f"Loading Whisper model '{self.model_size}'...", flush=True)
            self.model = await loop.run_in_executor(None, self._load_model)
            print(f"Whisper '{self.model_size}' loaded and ready (local transcription).")
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())

    def _load_model(self):
        from faster_whisper import WhisperModel
        return WhisperModel(self.model_size, device="cpu", compute_type="int8")

    async def send_audio(self, audio_bytes: bytes):
        """Buffer incoming audio and track speech/silence state."""
        async with self._lock:
            if not self._audio_buffer and self._clock_zero is not None:
                self._buffer_wall_start = time.monotonic() - self._clock_zero
            self._audio_buffer.extend(audio_bytes)

            # Energy-based VAD on this chunk
            chunk = np.frombuffer(audio_bytes, dtype=np.int16)
            rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))

            if rms > SILENCE_RMS_THRESHOLD:
                self._has_speech = True
                self._silence_start = None
            elif self._has_speech and self._silence_start is None:
                self._silence_start = time.monotonic()

    async def _process_loop(self):
        """Check periodically whether to transcribe buffered audio."""
        while self._running:
            await asyncio.sleep(0.3)

            should_process = False
            async with self._lock:
                buf_seconds = len(self._audio_buffer) / (SAMPLE_RATE * BYTES_PER_SAMPLE)

                if self._has_speech and buf_seconds >= MIN_SPEECH_S:
                    # Silence long enough → utterance boundary
                    if (self._silence_start is not None
                            and (time.monotonic() - self._silence_start) >= SILENCE_DURATION_S):
                        should_process = True
                    # Buffer too long → force transcribe
                    elif buf_seconds >= MAX_BUFFER_S:
                        should_process = True

            if should_process:
                await self._transcribe_buffer()

    async def _transcribe_buffer(self):
        """Extract buffered audio, run Whisper, fire callbacks."""
        async with self._lock:
            audio_bytes = bytes(self._audio_buffer)
            if self._clock_zero is not None and self._buffer_wall_start is not None:
                buffer_start = self._buffer_wall_start
            else:
                buffer_start = self._elapsed_seconds
            buffer_duration = len(audio_bytes) / (SAMPLE_RATE * BYTES_PER_SAMPLE)
            self._elapsed_seconds += buffer_duration
            self._audio_buffer.clear()
            self._buffer_wall_start = None
            self._has_speech = False
            self._silence_start = None

        if not audio_bytes:
            return

        # Convert int16 PCM → float32 [-1, 1] for Whisper
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Run Whisper in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        segments = await loop.run_in_executor(None, self._run_whisper, audio_np)

        for segment in segments:
            text = segment.text.strip()
            if text:
                result = TranscriptionResult(
                    text=text,
                    start=buffer_start + segment.start,
                    end=buffer_start + segment.end,
                    is_final=True,
                    speaker=self.speaker,
                )
                if self.on_transcript:
                    if asyncio.iscoroutinefunction(self.on_transcript):
                        await self.on_transcript(result)
                    else:
                        self.on_transcript(result)

    def _run_whisper(self, audio: np.ndarray) -> list:
        """Run faster-whisper transcription (called in thread pool)."""
        if self._transcribe_lock is not None:
            with self._transcribe_lock:
                return self._run_whisper_inner(audio)
        return self._run_whisper_inner(audio)

    def _run_whisper_inner(self, audio: np.ndarray) -> list:
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        return list(segments)

    async def close(self):
        """Stop processing and transcribe any remaining audio."""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        # Flush remaining audio
        if self._audio_buffer and self._has_speech:
            await self._transcribe_buffer()
        print("Local transcriber closed.")
