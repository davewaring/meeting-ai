"""Audio capture from BlackHole virtual audio device."""

import asyncio
import numpy as np
import sounddevice as sd
from config import SAMPLE_RATE, CHANNELS, DTYPE, CHUNK_DURATION_MS


def find_blackhole_device() -> dict | None:
    """Find the BlackHole 2ch audio device."""
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if "BlackHole" in d["name"] and d["max_input_channels"] >= CHANNELS:
            return {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
    return None


def get_capture_config() -> dict:
    """Return the audio capture configuration."""
    return {
        "sample_rate": SAMPLE_RATE,
        "channels": CHANNELS,
        "dtype": DTYPE,
    }


def capture_audio_chunk(duration_seconds: float = 2.0, device_index: int | None = None) -> np.ndarray | None:
    """Capture a single chunk of audio from BlackHole (blocking).

    Used for testing. For production streaming, use start_capture_stream().
    """
    if device_index is None:
        bh = find_blackhole_device()
        if bh is None:
            return None
        device_index = bh["index"]

    chunk_samples = int(SAMPLE_RATE * duration_seconds)
    recording = sd.rec(
        chunk_samples,
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=device_index,
    )
    sd.wait()
    return recording.flatten()


async def start_capture_stream(callback, stop_event: asyncio.Event):
    """Start streaming audio from BlackHole, calling callback with each chunk.

    Args:
        callback: async function that receives (audio_bytes: bytes) for each chunk
        stop_event: set this event to stop capture
    """
    bh = find_blackhole_device()
    if bh is None:
        raise RuntimeError(
            "BlackHole audio device not found. "
            "Install with: brew install blackhole-2ch"
        )

    chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
    loop = asyncio.get_event_loop()
    audio_queue = asyncio.Queue()

    def audio_callback(indata, frames, time_info, status):
        """Called by sounddevice for each audio chunk."""
        if status:
            print(f"Audio status: {status}")
        # Copy the data and put it in the async queue
        audio_bytes = indata.copy().tobytes()
        loop.call_soon_threadsafe(audio_queue.put_nowait, audio_bytes)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=bh["index"],
        blocksize=chunk_samples,
        callback=audio_callback,
    )

    print(f"Starting audio capture from: {bh['name']}")
    stream.start()

    try:
        while not stop_event.is_set():
            try:
                audio_bytes = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
                await callback(audio_bytes)
            except asyncio.TimeoutError:
                continue
    finally:
        stream.stop()
        stream.close()
        print("Audio capture stopped.")


if __name__ == "__main__":
    """Quick test: list devices and capture a short sample."""
    print("Available audio devices:")
    print(sd.query_devices())
    print()

    bh = find_blackhole_device()
    if bh:
        print(f"Found BlackHole: {bh}")
        print("Capturing 3 seconds of audio...")
        chunk = capture_audio_chunk(duration_seconds=3, device_index=bh["index"])
        if chunk is not None:
            peak = np.abs(chunk).max()
            rms = np.sqrt(np.mean(chunk.astype(float) ** 2))
            print(f"Captured {len(chunk)} samples, peak={peak}, RMS={rms:.1f}")
            if peak < 10:
                print("WARNING: Audio appears silent. Is Zoom playing audio through BlackHole?")
            else:
                print("Audio captured successfully!")
    else:
        print("BlackHole not found. Install with: brew install blackhole-2ch")
