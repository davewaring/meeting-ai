"""Phase 1 tests: Audio capture + Deepgram transcription."""

import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Test 1: BlackHole device detection ---

def test_blackhole_detected():
    """sounddevice must find a BlackHole audio device."""
    import sounddevice as sd
    devices = sd.query_devices()
    blackhole = [d for d in devices if "BlackHole" in d["name"]]
    assert len(blackhole) > 0, (
        "BlackHole not found in audio devices. "
        "Install with: brew install blackhole-2ch (then reboot)"
    )


# --- Test 2: Audio capture module loads and finds BlackHole ---

def test_find_blackhole_device():
    """audio_capture.find_blackhole_device() returns device info."""
    from audio_capture import find_blackhole_device
    device = find_blackhole_device()
    assert device is not None, "find_blackhole_device() returned None"
    assert "index" in device
    assert "name" in device
    assert "BlackHole" in device["name"]


# --- Test 3: Audio capture config is correct ---

def test_audio_capture_config():
    """Audio capture outputs 16kHz, mono, int16 PCM."""
    from audio_capture import get_capture_config
    config = get_capture_config()
    assert config["sample_rate"] == 16000, f"Expected 16kHz, got {config['sample_rate']}"
    assert config["channels"] == 1, f"Expected mono, got {config['channels']}"
    assert config["dtype"] == "int16", f"Expected int16, got {config['dtype']}"


# --- Test 4: Audio capture produces data ---

def test_audio_capture_produces_data():
    """Capture 1 second of audio from BlackHole, verify array returned."""
    from audio_capture import capture_audio_chunk, find_blackhole_device
    device = find_blackhole_device()
    if device is None:
        pytest.skip("BlackHole not available")

    chunk = capture_audio_chunk(duration_seconds=1, device_index=device["index"])
    assert chunk is not None, "No audio data returned"
    assert len(chunk) > 0, "Empty audio chunk"
    # Should be ~16000 samples for 1 second at 16kHz
    assert len(chunk) >= 15000, f"Too few samples: {len(chunk)} (expected ~16000)"


# --- Test 5: Deepgram API key is configured ---

def test_deepgram_api_key_configured():
    """DEEPGRAM_API_KEY must be set in .env."""
    from config import DEEPGRAM_API_KEY
    assert DEEPGRAM_API_KEY, (
        "DEEPGRAM_API_KEY not set. "
        "Copy .env.example to .env and add your key."
    )
    assert len(DEEPGRAM_API_KEY) > 10, "DEEPGRAM_API_KEY looks too short"


# --- Test 6: Deepgram transcribes test audio file ---

@pytest.mark.anyio
async def test_transcription_returns_text():
    """Send test audio to Deepgram batch API, verify text comes back."""
    from config import DEEPGRAM_API_KEY
    if not DEEPGRAM_API_KEY:
        pytest.skip("DEEPGRAM_API_KEY not set")

    from transcriber import transcribe_audio_file

    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "test_audio.wav"
    )
    if not os.path.exists(fixture_path):
        pytest.skip(f"Test audio not found: {fixture_path}")

    result = await transcribe_audio_file(fixture_path)
    assert result is not None, "No transcription result"
    assert len(result.strip()) > 0, "Empty transcription"
    # The test audio says "This is a test of the meeting AI transcription system"
    result_lower = result.lower()
    assert "test" in result_lower, f"Expected 'test' in transcript, got: {result}"
    print(f"Transcribed: {result}")
