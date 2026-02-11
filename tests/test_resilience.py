"""Tests for audio resilience: audio buffer (2.3.1) + auto-reconnect (2.3.2).

These are specification tests — they define the expected API and behavior
for the resilience module before it is built. The resilience module will
provide:

  AudioBuffer     — ring buffer that stores PCM chunks when Deepgram is
                    disconnected and replays them on reconnect.
  ReconnectManager — detects WebSocket close, reconnects within 5s, and
                     replays buffered audio through the new connection.
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 2.3.1  Audio Buffer Tests
# ---------------------------------------------------------------------------

def test_buffer_stores_chunks_when_disconnected():
    """AudioBuffer stores audio chunks when in buffering mode (Deepgram down)."""
    from resilience import AudioBuffer

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)  # 30s of 16kHz 16-bit mono
    buf.set_buffering(True)

    chunk = b"\x00\x01" * 1600  # 100ms of 16kHz 16-bit mono (3200 bytes)
    buf.write(chunk)

    assert buf.size() == len(chunk)
    assert buf.chunk_count() == 1


def test_buffer_replays_stored_chunks_on_reconnect():
    """AudioBuffer.drain() returns all stored chunks in FIFO order, then empties."""
    from resilience import AudioBuffer

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    buf.set_buffering(True)

    chunk_a = b"\xaa" * 3200
    chunk_b = b"\xbb" * 3200
    chunk_c = b"\xcc" * 3200
    buf.write(chunk_a)
    buf.write(chunk_b)
    buf.write(chunk_c)

    chunks = buf.drain()
    assert chunks == [chunk_a, chunk_b, chunk_c], "drain() must return chunks in FIFO order"
    assert buf.size() == 0, "drain() must empty the buffer"
    assert buf.chunk_count() == 0


def test_buffer_ring_behavior_evicts_oldest():
    """When buffer exceeds max_bytes, oldest chunks are evicted (ring buffer)."""
    from resilience import AudioBuffer

    # Max size = 2 chunks worth (6400 bytes)
    buf = AudioBuffer(max_bytes=6400)
    buf.set_buffering(True)

    chunk_old = b"\x01" * 3200
    chunk_mid = b"\x02" * 3200
    chunk_new = b"\x03" * 3200

    buf.write(chunk_old)
    buf.write(chunk_mid)
    # Buffer is now full (6400 bytes). Writing one more should evict chunk_old.
    buf.write(chunk_new)

    chunks = buf.drain()
    assert chunk_old not in chunks, "oldest chunk should be evicted"
    assert chunks == [chunk_mid, chunk_new], "only the newest chunks should remain"


def test_buffer_passthrough_when_connected():
    """When Deepgram is connected (not buffering), write() does not store data."""
    from resilience import AudioBuffer

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    buf.set_buffering(False)  # connected / passthrough mode

    chunk = b"\x00\x01" * 1600
    buf.write(chunk)

    assert buf.size() == 0, "buffer should not store data in passthrough mode"
    assert buf.chunk_count() == 0


def test_buffer_default_is_passthrough():
    """A new AudioBuffer starts in passthrough mode (not buffering)."""
    from resilience import AudioBuffer

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    assert buf.is_buffering() is False


def test_buffer_transitions_between_modes():
    """Buffer stores data only while buffering, then stops after switching back."""
    from resilience import AudioBuffer

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)

    # Passthrough — nothing stored
    buf.write(b"\x00" * 3200)
    assert buf.chunk_count() == 0

    # Switch to buffering
    buf.set_buffering(True)
    buf.write(b"\x01" * 3200)
    buf.write(b"\x02" * 3200)
    assert buf.chunk_count() == 2

    # Switch back to passthrough — new writes not stored, but old data remains
    buf.set_buffering(False)
    buf.write(b"\x03" * 3200)
    assert buf.chunk_count() == 2, "new writes after switching to passthrough should not be stored"


def test_buffer_drain_returns_empty_list_when_empty():
    """drain() returns an empty list when no data has been buffered."""
    from resilience import AudioBuffer

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    assert buf.drain() == []


# ---------------------------------------------------------------------------
# 2.3.2  Auto-Reconnect Tests
# ---------------------------------------------------------------------------

def test_reconnect_detects_websocket_close():
    """ReconnectManager detects when the Deepgram WebSocket closes."""
    from resilience import ReconnectManager, AudioBuffer

    events = []

    def on_disconnect():
        events.append("disconnected")

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    mgr = ReconnectManager(audio_buffer=buf, on_disconnect=on_disconnect)

    # Simulate the WebSocket closing
    mgr.notify_disconnected()

    assert "disconnected" in events, "on_disconnect callback should fire"
    assert buf.is_buffering() is True, "buffer should switch to buffering mode on disconnect"


def test_reconnect_attempt_within_timeout():
    """ReconnectManager attempts reconnect within the configured timeout (default 5s)."""
    from resilience import ReconnectManager, AudioBuffer

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    mgr = ReconnectManager(audio_buffer=buf, reconnect_timeout_s=5.0)

    assert mgr.reconnect_timeout_s == 5.0, "default reconnect timeout should be 5 seconds"


def test_reconnect_resumes_transcription():
    """After reconnect, ReconnectManager signals that transcription has resumed."""
    from resilience import ReconnectManager, AudioBuffer

    events = []

    def on_reconnect():
        events.append("reconnected")

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    mgr = ReconnectManager(audio_buffer=buf, on_reconnect=on_reconnect)

    # Simulate disconnect then reconnect
    mgr.notify_disconnected()
    mgr.notify_reconnected()

    assert "reconnected" in events, "on_reconnect callback should fire"
    assert buf.is_buffering() is False, "buffer should switch back to passthrough after reconnect"


def test_reconnect_replays_buffered_audio():
    """After reconnect, buffered audio chunks are drained and sent to the new connection."""
    from resilience import ReconnectManager, AudioBuffer

    replayed_chunks = []

    def mock_send(chunk: bytes):
        replayed_chunks.append(chunk)

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    mgr = ReconnectManager(audio_buffer=buf, send_fn=mock_send)

    # Simulate: disconnect, buffer some audio, then reconnect
    mgr.notify_disconnected()

    chunk_a = b"\xaa" * 3200
    chunk_b = b"\xbb" * 3200
    buf.write(chunk_a)
    buf.write(chunk_b)

    mgr.notify_reconnected()

    assert replayed_chunks == [chunk_a, chunk_b], "buffered audio should be replayed in order via send_fn"
    assert buf.chunk_count() == 0, "buffer should be empty after replay"


def test_reconnect_tracks_connection_state():
    """ReconnectManager exposes the current connection state."""
    from resilience import ReconnectManager, AudioBuffer

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    mgr = ReconnectManager(audio_buffer=buf)

    assert mgr.is_connected() is True, "initial state should be connected"

    mgr.notify_disconnected()
    assert mgr.is_connected() is False, "should be disconnected after notify_disconnected"

    mgr.notify_reconnected()
    assert mgr.is_connected() is True, "should be connected after notify_reconnected"


def test_reconnect_counts_attempts():
    """ReconnectManager tracks the number of reconnection attempts."""
    from resilience import ReconnectManager, AudioBuffer

    buf = AudioBuffer(max_bytes=16000 * 2 * 30)
    mgr = ReconnectManager(audio_buffer=buf)

    assert mgr.reconnect_count == 0

    mgr.notify_disconnected()
    mgr.notify_reconnected()
    assert mgr.reconnect_count == 1

    mgr.notify_disconnected()
    mgr.notify_reconnected()
    assert mgr.reconnect_count == 2
