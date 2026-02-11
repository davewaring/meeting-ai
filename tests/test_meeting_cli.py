"""Tests for meeting CLI: VTT export, CLI lifecycle."""

import sys
import os
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- VTT Export Tests ---

def test_vtt_format_basic():
    """format_vtt produces valid WebVTT with timestamps."""
    from vtt_export import format_vtt
    entries = [
        {"start_ms": 0, "end_ms": 3000, "text": "Hello world"},
        {"start_ms": 3500, "end_ms": 7000, "text": "Second line"},
    ]
    vtt = format_vtt(entries)
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:03.000" in vtt
    assert "Hello world" in vtt
    assert "Second line" in vtt


def test_vtt_format_with_speakers():
    """VTT includes <v Speaker N> voice tags."""
    from vtt_export import format_vtt
    entries = [
        {"start_ms": 0, "end_ms": 5000, "text": "First", "speaker": 0},
        {"start_ms": 5000, "end_ms": 10000, "text": "Second", "speaker": 1},
        {"start_ms": 10000, "end_ms": 15000, "text": "No speaker"},
    ]
    vtt = format_vtt(entries)
    assert "<v Speaker 0>First" in vtt
    assert "<v Speaker 1>Second" in vtt
    # Entry without speaker should NOT have voice tag
    lines = vtt.split("\n")
    no_speaker_line = [l for l in lines if "No speaker" in l][0]
    assert "<v " not in no_speaker_line


def test_vtt_save_to_directory():
    """save_vtt creates VTT file in YYYY-MM subdirectory."""
    from vtt_export import save_vtt
    entries = [
        {"start_ms": 0, "end_ms": 3000, "text": "Test entry"},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_vtt(entries, topic="test-meeting", output_dir=tmpdir)
        assert os.path.exists(path)
        expected_month = datetime.now().strftime("%Y-%m")
        assert expected_month in path
        content = open(path).read()
        assert content.startswith("WEBVTT")
        assert "Test entry" in content


def test_vtt_save_filename_format():
    """VTT filename includes date, time, and topic."""
    from vtt_export import save_vtt
    entries = [{"start_ms": 0, "end_ms": 1000, "text": "test"}]
    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_vtt(entries, topic="weekly standup", output_dir=tmpdir)
        filename = os.path.basename(path)
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in filename
        assert "weekly-standup" in filename
        assert filename.endswith(".vtt")


def test_vtt_empty_entries():
    """format_vtt with empty entries produces just the header."""
    from vtt_export import format_vtt
    vtt = format_vtt([])
    assert vtt.startswith("WEBVTT")
    lines = [l for l in vtt.strip().split("\n") if l]
    assert len(lines) == 1  # Just "WEBVTT"


# --- Meeting CLI Tests ---

def test_meeting_module_importable():
    """meeting.py module is importable without errors."""
    import meeting
    assert hasattr(meeting, "run_meeting")
    assert hasattr(meeting, "main")
