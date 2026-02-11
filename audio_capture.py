"""Audio capture from BlackHole virtual audio device."""

import asyncio
import numpy as np
import sounddevice as sd
from config import SAMPLE_RATE, CHANNELS, DTYPE, CHUNK_DURATION_MS, SPEAKER_VOLUME, MIC_VOLUME


def find_blackhole_device() -> dict | None:
    """Find the BlackHole 2ch audio device."""
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if "BlackHole" in d["name"] and d["max_input_channels"] >= CHANNELS:
            return {"index": i, "name": d["name"], "channels": d["max_input_channels"]}
    return None


def find_mic_device() -> dict | None:
    """Find the default microphone input device."""
    devices = sd.query_devices()
    # Prefer the system default input
    try:
        default_idx = sd.default.device[0]  # default input device index
        if default_idx is not None and default_idx >= 0:
            d = devices[default_idx]
            if d["max_input_channels"] >= CHANNELS and "BlackHole" not in d["name"]:
                return {"index": default_idx, "name": d["name"], "channels": d["max_input_channels"]}
    except Exception:
        pass
    # Fallback: find any built-in mic
    for i, d in enumerate(devices):
        if d["max_input_channels"] >= CHANNELS and "Microphone" in d["name"]:
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
    """Start streaming audio from BlackHole + microphone, mixed into one stream.

    Captures both sides of the conversation:
    - BlackHole: other participants' audio (speaker output)
    - Microphone: your own voice

    Both sources are mixed together before sending to the transcription callback.

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

    mic = find_mic_device()

    chunk_samples = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
    loop = asyncio.get_event_loop()

    # Separate queues for each source
    bh_queue = asyncio.Queue()
    mic_queue = asyncio.Queue()

    def bh_callback(indata, frames, time_info, status):
        if status:
            print(f"Audio status (blackhole): {status}")
        loop.call_soon_threadsafe(bh_queue.put_nowait, indata.copy())

    def mic_callback(indata, frames, time_info, status):
        if status:
            print(f"Audio status (mic): {status}")
        loop.call_soon_threadsafe(mic_queue.put_nowait, indata.copy())

    # BlackHole stream (other participants)
    bh_stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        device=bh["index"],
        blocksize=chunk_samples,
        callback=bh_callback,
    )

    # Mic stream (your voice)
    mic_stream = None
    if mic:
        mic_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            device=mic["index"],
            blocksize=chunk_samples,
            callback=mic_callback,
        )

    print(f"Starting audio capture from: {bh['name']}")
    bh_stream.start()
    if mic_stream:
        print(f"Starting mic capture from: {mic['name']}")
        mic_stream.start()
    else:
        print("No microphone found — capturing speaker audio only.")

    try:
        while not stop_event.is_set():
            try:
                # Wait for a BlackHole chunk (primary clock source)
                bh_data = await asyncio.wait_for(bh_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            # Grab the latest mic chunk if available (non-blocking)
            mic_data = None
            if mic_stream:
                try:
                    while not mic_queue.empty():
                        mic_data = mic_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass

            # Apply software volume and mix
            bh_scaled = (bh_data.astype(np.int32) * SPEAKER_VOLUME).astype(np.int32)
            if mic_data is not None:
                mic_scaled = (mic_data.astype(np.int32) * MIC_VOLUME).astype(np.int32)
                mixed = np.clip(bh_scaled + mic_scaled, -32768, 32767).astype(np.int16)
            else:
                mixed = np.clip(bh_scaled, -32768, 32767).astype(np.int16)

            await callback(mixed.tobytes())
    finally:
        bh_stream.stop()
        bh_stream.close()
        if mic_stream:
            mic_stream.stop()
            mic_stream.close()
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
