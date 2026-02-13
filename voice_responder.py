"""TTS generation + audio encoding for speaking into the Twilio call."""

import asyncio
import struct

from openai import AsyncOpenAI

from config import TTS_PROVIDER, TTS_VOICE, TWILIO_SAMPLE_RATE, OPENAI_API_KEY

# mulaw encoding constants
_MULAW_BIAS = 0x84
_MULAW_CLIP = 32635
_MULAW_TABLE = [
    0, 0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
]


def _encode_mulaw_sample(sample: int) -> int:
    """Encode a single PCM16 sample to mulaw."""
    sign = 0
    if sample < 0:
        sign = 0x80
        sample = -sample
    if sample > _MULAW_CLIP:
        sample = _MULAW_CLIP
    sample += _MULAW_BIAS
    exponent = _MULAW_TABLE[(sample >> 7) & 0xFF]
    mantissa = (sample >> (exponent + 3)) & 0x0F
    return ~(sign | (exponent << 4) | mantissa) & 0xFF


def pcm16_to_mulaw(pcm_data: bytes) -> bytes:
    """Convert PCM16 audio to mulaw encoding.

    Args:
        pcm_data: Raw PCM16 (signed 16-bit little-endian) audio bytes.
    Returns:
        mulaw-encoded audio bytes (1 byte per sample).
    """
    num_samples = len(pcm_data) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm_data)
    return bytes(_encode_mulaw_sample(s) for s in samples)


def resample_to_8khz(pcm_data: bytes, source_rate: int) -> bytes:
    """Resample PCM16 audio to 8000 Hz for Twilio using linear interpolation.

    Args:
        pcm_data: Raw PCM16 audio bytes at source_rate.
        source_rate: Original sample rate in Hz.
    Returns:
        Resampled PCM16 audio at 8000 Hz.
    """
    if source_rate == TWILIO_SAMPLE_RATE:
        return pcm_data

    num_samples = len(pcm_data) // 2
    samples = struct.unpack(f"<{num_samples}h", pcm_data)
    ratio = source_rate / TWILIO_SAMPLE_RATE
    out_count = int(num_samples / ratio)
    out = []
    for i in range(out_count):
        src_pos = i * ratio
        idx = int(src_pos)
        frac = src_pos - idx
        if idx + 1 < num_samples:
            val = samples[idx] * (1 - frac) + samples[idx + 1] * frac
        else:
            val = samples[idx]
        out.append(max(-32768, min(32767, int(val))))
    return struct.pack(f"<{len(out)}h", *out)


# OpenAI TTS outputs PCM at 24kHz by default
OPENAI_TTS_SAMPLE_RATE = 24000

# Twilio Media Streams send audio in ~20ms chunks (160 bytes of mulaw at 8kHz)
TWILIO_CHUNK_SIZE = 160


class VoiceResponder:
    """Generates speech audio and sends it through the media stream.

    Uses OpenAI TTS to generate speech, converts to mulaw 8kHz,
    and streams into the Twilio call in real time.
    """

    def __init__(self, media_stream):
        """
        Args:
            media_stream: MediaStreamServer instance for sending audio.
        """
        self._media_stream = media_stream
        self._speaking = False
        self._client = None
        if OPENAI_API_KEY:
            self._client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    async def speak(self, text: str):
        """Generate TTS audio and play it into the call.

        Args:
            text: The text to speak.
        """
        if not self._media_stream.is_connected:
            print("  [voice] Cannot speak - not connected to call")
            return

        if not self._client:
            print("  [voice] Cannot speak - OPENAI_API_KEY not set")
            return

        self._speaking = True
        try:
            # Generate speech via OpenAI TTS
            pcm_data = await self._generate_speech(text)
            if not pcm_data:
                return

            # Resample 24kHz -> 8kHz, then convert to mulaw
            pcm_8khz = resample_to_8khz(pcm_data, OPENAI_TTS_SAMPLE_RATE)
            mulaw_audio = pcm16_to_mulaw(pcm_8khz)

            # Stream in chunks to match Twilio's expected pacing
            await self._stream_audio(mulaw_audio)

        except Exception as e:
            print(f"  [voice] Error: {e}")
        finally:
            self._speaking = False

    async def _generate_speech(self, text: str) -> bytes | None:
        """Call OpenAI TTS and return raw PCM16 audio bytes."""
        try:
            response = await self._client.audio.speech.create(
                model="tts-1",
                voice=TTS_VOICE,
                input=text,
                response_format="pcm",
            )
            return response.content
        except Exception as e:
            print(f"  [voice] TTS error: {e}")
            return None

    async def _stream_audio(self, mulaw_audio: bytes):
        """Send mulaw audio to Twilio in paced chunks.

        Twilio expects ~20ms of audio per message (160 bytes at 8kHz mulaw).
        We pace the sends to avoid overwhelming the buffer.
        """
        offset = 0
        while offset < len(mulaw_audio) and self._speaking:
            chunk = mulaw_audio[offset:offset + TWILIO_CHUNK_SIZE]
            await self._media_stream.send_audio(chunk)
            offset += TWILIO_CHUNK_SIZE
            # Pace at ~20ms per chunk to match real-time playback
            await asyncio.sleep(0.02)

    async def stop(self):
        """Stop any in-progress speech."""
        self._speaking = False
        if self._media_stream.is_connected:
            await self._media_stream.clear_audio()
