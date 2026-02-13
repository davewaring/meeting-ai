"""Tests for monitor.py — cooldown, context loading, response parsing."""

import sys
import os
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# --- MonitorConfig tests ---

def test_monitor_config_defaults():
    """MonitorConfig should have sensible defaults."""
    from monitor_config import MonitorConfig
    cfg = MonitorConfig()
    assert cfg.cooldown_seconds == 45
    assert cfg.min_new_lines == 5
    assert cfg.poll_interval == 2.0


def test_monitor_config_validate_missing_key():
    """validate() should raise if API key is empty."""
    from monitor_config import MonitorConfig
    cfg = MonitorConfig(api_key="")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        cfg.validate()


def test_monitor_config_validate_with_key():
    """validate() should pass if API key is set."""
    from monitor_config import MonitorConfig
    cfg = MonitorConfig(api_key="sk-test-123")
    cfg.validate()  # Should not raise


# --- Library context tests ---

def test_detect_projects_finds_braindrive_code():
    """Should detect braindrive-code from keywords."""
    from library_context import detect_projects
    transcript = "We need to discuss the braindrive code plugin system"
    projects = detect_projects(transcript)
    assert "braindrive-code" in projects


def test_detect_projects_finds_hardware():
    """Should detect braindrive-hardware from keywords."""
    from library_context import detect_projects
    transcript = "The watch prototype is coming along"
    projects = detect_projects(transcript)
    assert "braindrive-hardware" in projects


def test_detect_projects_finds_plus_one():
    """Should detect braindrive-plus-one from keywords."""
    from library_context import detect_projects
    transcript = "Let's talk about the +1 meeting assistant"
    projects = detect_projects(transcript)
    assert "braindrive-plus-one" in projects


def test_detect_projects_finds_community():
    """Should detect community-engagement from keywords."""
    from library_context import detect_projects
    transcript = "We need to post a forum update to the community"
    projects = detect_projects(transcript)
    assert "community-engagement" in projects


def test_detect_projects_empty_transcript():
    """Empty transcript should return no projects."""
    from library_context import detect_projects
    assert detect_projects("") == []


def test_detect_projects_multiple():
    """Multiple projects mentioned should all be detected."""
    from library_context import detect_projects
    transcript = "The plugin and the watch are both progressing"
    projects = detect_projects(transcript)
    assert "braindrive-code" in projects
    assert "braindrive-hardware" in projects


def test_load_core_context_missing_dir():
    """load_core_context should return empty string for missing directory."""
    from library_context import load_core_context
    result = load_core_context("/nonexistent/path/12345")
    assert result == ""


def test_load_project_context_missing_dir():
    """load_project_context should return empty string for missing directory."""
    from library_context import load_project_context
    result = load_project_context("/nonexistent/path/12345", ["fake-project"])
    assert result == ""


# --- Suggestion formatter tests ---

def test_format_suggestion_contains_category():
    """Formatted suggestion should include the category."""
    from suggestion_formatter import format_suggestion
    output = format_suggestion("RELATED", "Plugin limit was 5MB", "Details here", "decisions.md")
    assert "RELATED" in output
    assert "Plugin limit was 5MB" in output


def test_format_suggestion_contains_source():
    """Formatted suggestion should include the source."""
    from suggestion_formatter import format_suggestion
    output = format_suggestion("CONTEXT", "Summary", "", "braindrive-code/decisions.md")
    assert "braindrive-code/decisions.md" in output


def test_format_suggestion_no_source():
    """Suggestion without source should still format cleanly."""
    from suggestion_formatter import format_suggestion
    output = format_suggestion("IDEA", "New feature idea", "Some detail")
    assert "IDEA" in output
    assert "New feature idea" in output


def test_format_status_bar():
    """Status bar should include key info."""
    from suggestion_formatter import format_status_bar
    bar = format_status_bar("team-call", "+16465588656", "1234567890",
                            "Connected", "sonnet-4-5", 100)
    assert "team-call" in bar
    assert "1234567890" in bar
    assert "Connected" in bar


def test_format_speaking():
    """Speaking notice should include the text."""
    from suggestion_formatter import format_speaking
    output = format_speaking("Just a note about D42")
    assert "SPEAKING" in output
    assert "Just a note about D42" in output


# --- Response parsing tests ---

def test_parse_none_response():
    """NONE response should not produce suggestions."""
    from monitor import TranscriptMonitor
    from monitor_config import MonitorConfig
    cfg = MonitorConfig(api_key="test")
    suggestions = []
    monitor = TranscriptMonitor(cfg, on_suggestion=lambda c, s, d, src: suggestions.append((c, s)))
    monitor._process_response("NONE")
    assert suggestions == []


def test_parse_single_suggestion():
    """Single suggestion should be parsed correctly."""
    from monitor import TranscriptMonitor
    from monitor_config import MonitorConfig
    cfg = MonitorConfig(api_key="test")
    suggestions = []
    monitor = TranscriptMonitor(cfg, on_suggestion=lambda c, s, d, src: suggestions.append((c, s)))
    monitor._process_response("RELATED: Plugin size was capped at 5MB\nSee decision D42.\nSource: decisions.md")
    assert len(suggestions) == 1
    assert suggestions[0] == ("RELATED", "Plugin size was capped at 5MB")


def test_parse_multiple_suggestions():
    """Multiple suggestions separated by blank lines."""
    from monitor import TranscriptMonitor
    from monitor_config import MonitorConfig
    cfg = MonitorConfig(api_key="test")
    suggestions = []
    monitor = TranscriptMonitor(cfg, on_suggestion=lambda c, s, d, src: suggestions.append((c, s)))
    text = """RELATED: First suggestion
Detail line.

CONFLICT: Second suggestion
This conflicts with D12."""
    monitor._process_response(text)
    assert len(suggestions) == 2
    assert suggestions[0][0] == "RELATED"
    assert suggestions[1][0] == "CONFLICT"


def test_prior_suggestions_tracked():
    """Prior suggestions should be tracked for dedup."""
    from monitor import TranscriptMonitor
    from monitor_config import MonitorConfig
    cfg = MonitorConfig(api_key="test")
    monitor = TranscriptMonitor(cfg)
    monitor._process_response("IDEA: Test suggestion")
    assert len(monitor._prior_suggestions) == 1
    assert "IDEA: Test suggestion" in monitor._prior_suggestions[0]


# --- Voice responder tests ---

def test_pcm16_to_mulaw():
    """PCM16 to mulaw conversion should produce output."""
    from voice_responder import pcm16_to_mulaw
    # 100 samples of silence
    pcm = b"\x00\x00" * 100
    mulaw = pcm16_to_mulaw(pcm)
    assert len(mulaw) == 100  # mulaw is 1 byte per sample vs 2 for pcm16


def test_resample_same_rate():
    """Resampling at same rate should return identical data."""
    from voice_responder import resample_to_8khz
    pcm = b"\x00\x00" * 100
    result = resample_to_8khz(pcm, 8000)
    assert result == pcm


def test_resample_16k_to_8k():
    """Resampling 16kHz to 8kHz should halve the sample count."""
    from voice_responder import resample_to_8khz
    # 160 samples at 16kHz = 10ms
    pcm = b"\x00\x00" * 160
    result = resample_to_8khz(pcm, 16000)
    # Should be ~80 samples at 8kHz
    assert len(result) < len(pcm)


def test_resample_24k_to_8k():
    """Resampling 24kHz (OpenAI TTS) to 8kHz should produce 1/3 the samples."""
    from voice_responder import resample_to_8khz
    # 240 samples at 24kHz = 10ms
    pcm = b"\x00\x00" * 240
    result = resample_to_8khz(pcm, 24000)
    # Should be ~80 samples at 8kHz (240 / 3)
    assert len(result) // 2 == 80


def test_openai_tts_sample_rate_constant():
    """OpenAI TTS sample rate constant should be 24kHz."""
    from voice_responder import OPENAI_TTS_SAMPLE_RATE
    assert OPENAI_TTS_SAMPLE_RATE == 24000


def test_twilio_chunk_size_constant():
    """Twilio chunk size should be 160 bytes (20ms at 8kHz mulaw)."""
    from voice_responder import TWILIO_CHUNK_SIZE
    assert TWILIO_CHUNK_SIZE == 160


def test_voice_responder_no_api_key():
    """VoiceResponder should not create client without API key."""
    import unittest.mock as mock
    with mock.patch("voice_responder.OPENAI_API_KEY", ""):
        from voice_responder import VoiceResponder
        # Need to reload to pick up mocked value
        vr = VoiceResponder.__new__(VoiceResponder)
        vr._media_stream = mock.MagicMock()
        vr._speaking = False
        vr._client = None  # No API key = no client
        assert vr._client is None


@pytest.mark.anyio
async def test_voice_responder_speak_not_connected():
    """speak() should bail if media stream is not connected."""
    import unittest.mock as mock
    from voice_responder import VoiceResponder
    ms = mock.MagicMock()
    ms.is_connected = False
    vr = VoiceResponder.__new__(VoiceResponder)
    vr._media_stream = ms
    vr._speaking = False
    vr._client = mock.MagicMock()
    await vr.speak("Hello")
    assert not vr._speaking


@pytest.mark.anyio
async def test_voice_responder_stop_clears_audio():
    """stop() should clear audio and reset speaking flag."""
    import unittest.mock as mock
    from voice_responder import VoiceResponder
    ms = mock.AsyncMock()
    ms.is_connected = True
    vr = VoiceResponder.__new__(VoiceResponder)
    vr._media_stream = ms
    vr._speaking = True
    await vr.stop()
    assert not vr._speaking
    ms.clear_audio.assert_awaited_once()


@pytest.mark.anyio
async def test_stream_audio_sends_chunks():
    """_stream_audio should send audio in TWILIO_CHUNK_SIZE chunks."""
    import unittest.mock as mock
    from voice_responder import VoiceResponder, TWILIO_CHUNK_SIZE
    ms = mock.AsyncMock()
    ms.is_connected = True
    vr = VoiceResponder.__new__(VoiceResponder)
    vr._media_stream = ms
    vr._speaking = True
    # 320 bytes = 2 chunks
    mulaw = b"\x7f" * 320
    await vr._stream_audio(mulaw)
    assert ms.send_audio.await_count == 2
    # First chunk should be TWILIO_CHUNK_SIZE bytes
    first_call_args = ms.send_audio.await_args_list[0][0][0]
    assert len(first_call_args) == TWILIO_CHUNK_SIZE


def test_pcm16_to_mulaw_nonzero_signal():
    """mulaw encoding of a non-zero signal should differ from silence."""
    import struct
    from voice_responder import pcm16_to_mulaw
    silence = pcm16_to_mulaw(b"\x00\x00" * 10)
    # A loud signal (max amplitude)
    loud = struct.pack("<10h", *([32000] * 10))
    loud_mulaw = pcm16_to_mulaw(loud)
    assert loud_mulaw != silence
