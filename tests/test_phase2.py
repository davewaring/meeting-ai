"""Phase 2 tests: Web UI, transcript manager, VTT export."""

import sys
import os
import pytest
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Test 1: Transcript manager buffers entries correctly ---

def test_transcript_buffer():
    """Entries are buffered in order and retrievable."""
    from transcript_mgr import TranscriptManager
    mgr = TranscriptManager()
    mgr.add_entry(start_ms=0, end_ms=2000, text="First")
    mgr.add_entry(start_ms=2000, end_ms=4000, text="Second")
    entries = mgr.get_entries()
    assert len(entries) == 2
    assert entries[0]["text"] == "First"
    assert entries[1]["text"] == "Second"
    assert entries[0]["start_ms"] == 0


# --- Test 2: VTT export produces valid format ---

def test_vtt_export_format():
    """Transcript manager exports valid WebVTT."""
    from transcript_mgr import TranscriptManager
    mgr = TranscriptManager()
    mgr.add_entry(start_ms=0, end_ms=3000, text="Hello, this is a test.")
    mgr.add_entry(start_ms=3500, end_ms=7000, text="Second line of transcript.")
    mgr.add_entry(start_ms=8000, end_ms=12000, text="Third entry here.")
    vtt = mgr.export_vtt()
    assert vtt.startswith("WEBVTT"), "Missing WEBVTT header"
    assert "00:00:00.000 --> 00:00:03.000" in vtt, "Missing first timestamp"
    assert "Hello, this is a test." in vtt
    assert "Second line of transcript." in vtt
    lines = vtt.strip().split("\n")
    assert len(lines) >= 8, f"Expected at least 8 lines, got {len(lines)}"


# --- Test 3: VTT file saved to correct Library path ---

def test_vtt_saved_to_library():
    """After export, VTT file exists in transcripts/YYYY-MM/."""
    import tempfile
    from transcript_mgr import TranscriptManager
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = TranscriptManager(library_path=tmpdir)
        mgr.add_entry(start_ms=0, end_ms=3000, text="Test entry.")
        filepath = mgr.save_vtt(meeting_title="test-meeting")
        assert os.path.exists(filepath), f"VTT file not found at {filepath}"
        expected_month = datetime.now().strftime("%Y-%m")
        assert expected_month in filepath, f"File not in YYYY-MM folder: {filepath}"
        with open(filepath) as f:
            content = f.read()
        assert content.startswith("WEBVTT"), "Saved file is not valid VTT"


# --- Test 4: Server starts and serves UI ---

@pytest.mark.anyio
async def test_server_starts_and_serves_ui():
    """GET / returns HTML with the expected UI elements."""
    from httpx import AsyncClient, ASGITransport
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8910") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "Start" in html, "Missing Start button"
    assert "Stop" in html, "Missing Stop button"
    assert "transcript" in html.lower(), "Missing transcript panel"
    assert "chat" in html.lower(), "Missing chat panel"


# --- Test 5: Status endpoint works ---

@pytest.mark.anyio
async def test_status_endpoint():
    """GET /api/status returns valid state."""
    from httpx import AsyncClient, ASGITransport
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8910") as client:
        response = await client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "state" in data
    assert data["state"] in ("idle", "recording", "processing")


# --- Test 6: Full text concatenation ---

def test_transcript_full_text():
    """get_full_text() joins all entries."""
    from transcript_mgr import TranscriptManager
    mgr = TranscriptManager()
    mgr.add_entry(start_ms=0, end_ms=2000, text="Hello world")
    mgr.add_entry(start_ms=2000, end_ms=4000, text="second sentence")
    full = mgr.get_full_text()
    assert full == "Hello world second sentence"
