"""Tests for twilio_caller.py — TwiML generation and DTMF sequences."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_build_twiml_contains_meeting_id():
    """TwiML should include the meeting ID in DTMF digits."""
    from twilio_caller import build_twiml
    twiml = build_twiml("123 456 7890", "wss://example.ngrok.io/stream")
    assert "1234567890" in twiml


def test_build_twiml_strips_spaces_and_dashes():
    """Meeting ID with spaces and dashes should be cleaned to digits only."""
    from twilio_caller import build_twiml
    twiml = build_twiml("123-456-7890", "wss://example.ngrok.io/stream")
    assert "123-456-7890" not in twiml
    assert "1234567890" in twiml


def test_build_twiml_dtmf_sequence():
    """DTMF should be: wait + meeting ID + # + wait + # (skip participant ID)."""
    from twilio_caller import build_twiml
    twiml = build_twiml("1234567890", "wss://test.io/ws")
    # Should contain meeting ID followed by # and trailing #
    assert "1234567890#" in twiml
    assert twiml.count("#") >= 2  # at least two # signs (meeting ID + skip participant)


def test_build_twiml_has_stream_url():
    """TwiML should include the WebSocket stream URL."""
    from twilio_caller import build_twiml
    ws_url = "wss://abc123.ngrok.io/stream"
    twiml = build_twiml("1234567890", ws_url)
    assert ws_url in twiml


def test_build_twiml_has_pause():
    """TwiML should have Pause elements for Zoom greeting."""
    from twilio_caller import build_twiml
    twiml = build_twiml("1234567890", "wss://test.io/ws")
    assert "<Pause" in twiml


def test_build_twiml_has_connect_stream():
    """TwiML should use <Connect><Stream> for media streaming."""
    from twilio_caller import build_twiml
    twiml = build_twiml("1234567890", "wss://test.io/ws")
    assert "<Connect>" in twiml
    assert "<Stream" in twiml


def test_build_twiml_is_valid_xml():
    """TwiML should be parseable XML."""
    import xml.etree.ElementTree as ET
    from twilio_caller import build_twiml
    twiml = build_twiml("1234567890", "wss://test.io/ws")
    root = ET.fromstring(twiml)
    assert root.tag == "Response"
