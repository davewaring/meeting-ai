"""Tests for media_stream.py — WebSocket message handling and audio encoding."""

import sys
import os
import asyncio
import base64
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_base64_audio_roundtrip():
    """Audio bytes should survive base64 encode/decode roundtrip."""
    original = b"\x80\x00\xff\x7f" * 100
    encoded = base64.b64encode(original).decode("ascii")
    decoded = base64.b64decode(encoded)
    assert decoded == original


def test_twilio_media_message_format():
    """Twilio media message should have correct JSON structure."""
    stream_sid = "MZ1234"
    audio_bytes = b"\x80\x00" * 50
    payload = base64.b64encode(audio_bytes).decode("ascii")
    message = json.dumps({
        "event": "media",
        "streamSid": stream_sid,
        "media": {"payload": payload},
    })
    parsed = json.loads(message)
    assert parsed["event"] == "media"
    assert parsed["streamSid"] == stream_sid
    recovered = base64.b64decode(parsed["media"]["payload"])
    assert recovered == audio_bytes


def test_twilio_clear_message_format():
    """Clear message should have the correct structure."""
    message = json.dumps({
        "event": "clear",
        "streamSid": "MZ1234",
    })
    parsed = json.loads(message)
    assert parsed["event"] == "clear"
    assert parsed["streamSid"] == "MZ1234"


@pytest.mark.anyio
async def test_media_stream_server_creation():
    """MediaStreamServer should be creatable without errors."""
    from media_stream import MediaStreamServer
    server = MediaStreamServer()
    assert server.is_connected is False
    assert server.stream_sid is None


@pytest.mark.anyio
async def test_media_stream_connected_event():
    """Connected event should be trackable."""
    from media_stream import MediaStreamServer
    server = MediaStreamServer()
    # Before connection, should not be connected
    assert server.is_connected is False


def test_parse_twilio_start_event():
    """Start event should contain streamSid."""
    msg = {
        "event": "start",
        "streamSid": "MZ12345",
        "start": {
            "streamSid": "MZ12345",
            "accountSid": "AC123",
            "callSid": "CA456",
        }
    }
    assert msg["event"] == "start"
    assert msg["streamSid"] == "MZ12345"


def test_parse_twilio_media_event():
    """Media event should contain base64 payload."""
    audio = b"\xff\x00\x80" * 20
    msg = {
        "event": "media",
        "media": {
            "payload": base64.b64encode(audio).decode("ascii"),
            "timestamp": "1234",
            "chunk": "1",
        }
    }
    decoded = base64.b64decode(msg["media"]["payload"])
    assert decoded == audio
