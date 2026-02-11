"""Phase 3 tests: AI chat, Library search, action notes, auto-processing."""

import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Library Search Tests ---

# Test 1: Library search returns results for known content
def test_library_search_finds_content():
    """Search for a term known to exist in the Library."""
    from library_search import search_library
    results = search_library("plugin architecture", library_path="~/BrainDrive-Library")
    assert len(results) > 0, "No results for 'plugin architecture' — should match spec/decision docs"
    for r in results:
        assert "file" in r, "Result missing 'file' field"
        assert "snippet" in r, "Result missing 'snippet' field"
        assert len(r["snippet"]) > 0, "Empty snippet"


# Test 2: Library search returns empty for nonsense query
def test_library_search_no_results():
    """Search for gibberish returns empty list, not an error."""
    from library_search import search_library
    results = search_library("qwertyuiop_absolutely_nothing_matches_this_98765")
    assert isinstance(results, list)
    assert len(results) == 0


# Test 3: Library search results are capped
def test_library_search_result_limit():
    """Results should be limited to top-N (not dump the whole Library)."""
    from library_search import search_library
    results = search_library("BrainDrive", library_path="~/BrainDrive-Library")
    assert len(results) <= 10, f"Too many results ({len(results)}) — should cap at 10"


# --- Chat Handler Tests ---

# Test 4: Chat handler returns response for a question
@pytest.mark.anyio
async def test_chat_responds_to_question():
    """Send a question with fake transcript, get AI response back."""
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        pytest.skip("ANTHROPIC_API_KEY not set")

    from chat_handler import handle_chat_message
    fake_transcript = "Dave J said the MCP server is ready. Nav mentioned node_modules bloat."
    response = await handle_chat_message(
        message="What did Dave J say?",
        transcript_text=fake_transcript,
    )
    assert response is not None, "No response from chat handler"
    assert len(response) > 10, "Response too short"
    assert "MCP" in response or "Dave" in response or "server" in response.lower(), (
        "Response doesn't reference transcript content"
    )


# Test 5: Note intent detected correctly
def test_note_intent_detection():
    """Messages starting with 'note', 'make a note', 'capture', 'remind' are classified as notes."""
    from chat_handler import detect_intent
    assert detect_intent("make a note to update the spec") == "note"
    assert detect_intent("note: Dave said the deadline is March") == "note"
    assert detect_intent("capture this — we agreed on the approach") == "note"
    assert detect_intent("remind me to follow up with Nav") == "note"
    assert detect_intent("What did we decide about the timeline?") == "question"
    assert detect_intent("Summarize the discussion so far") == "question"


# Test 6: Action note captured with transcript context
def test_action_note_capture():
    """Notes store the message + surrounding transcript context."""
    from chat_handler import NoteManager
    mgr = NoteManager()
    fake_transcript_entries = [
        {"start_ms": 0, "text": "Let's push the deadline to March 1."},
        {"start_ms": 5000, "text": "That gives us three more weeks."},
        {"start_ms": 10000, "text": "Agreed, March 1 it is."},
    ]
    note = mgr.capture_note(
        message="make a note to update the spec with new March 1 deadline",
        transcript_entries=fake_transcript_entries,
        timestamp_ms=12000,
    )
    assert note is not None
    assert "March 1" in note["message"]
    assert len(note["context"]) > 0, "Note missing transcript context"
    assert note["timestamp_ms"] == 12000


# Test 7: Notes endpoint returns all captured notes
@pytest.mark.anyio
async def test_notes_endpoint():
    """GET /api/notes returns list of captured notes."""
    from httpx import AsyncClient, ASGITransport
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8910") as client:
        response = await client.get("/api/notes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list), "Notes endpoint should return a list"


# Test 8: Chat endpoint returns response
@pytest.mark.anyio
async def test_chat_endpoint():
    """POST /api/chat with a message returns AI response."""
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        pytest.skip("ANTHROPIC_API_KEY not set")

    from httpx import AsyncClient, ASGITransport
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost:8910") as client:
        response = await client.post("/api/chat", json={"message": "What is BrainDrive?"})
    assert response.status_code == 200
    data = response.json()
    assert "response" in data, "Missing 'response' field"
    assert len(data["response"]) > 0, "Empty AI response"


# Test 9: Chat doesn't crash with empty transcript
@pytest.mark.anyio
async def test_chat_with_empty_transcript():
    """AI should handle questions when no transcript exists yet."""
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        pytest.skip("ANTHROPIC_API_KEY not set")

    from chat_handler import handle_chat_message
    response = await handle_chat_message(
        message="What are we discussing?",
        transcript_text="",
    )
    assert response is not None
    assert len(response) > 0, "Should respond even with empty transcript"


# Test 10: Auto-processing produces output file
@pytest.mark.anyio
async def test_auto_processing_output():
    """After VTT export, processing should produce a summary/extraction file."""
    from config import ANTHROPIC_API_KEY
    if not ANTHROPIC_API_KEY:
        pytest.skip("ANTHROPIC_API_KEY not set")

    import tempfile
    from transcript_mgr import TranscriptManager, auto_process_transcript
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = TranscriptManager(library_path=tmpdir)
        mgr.add_entry(start_ms=0, end_ms=5000, text="We decided to use Deepgram for transcription.")
        mgr.add_entry(start_ms=5000, end_ms=10000, text="Nav will fix the node modules issue by Friday.")
        mgr.add_entry(start_ms=10000, end_ms=15000, text="New idea: add a mobile companion app.")
        vtt_path = mgr.save_vtt(meeting_title="test-meeting")
        output_path = await auto_process_transcript(vtt_path)
        assert os.path.exists(output_path), f"Processing output not found at {output_path}"
        with open(output_path) as f:
            content = f.read()
        assert len(content) > 50, "Processing output too short"


# --- Library Search Keyword Extraction Tests ---

# Test 11: Natural language query gets converted to keywords
def test_library_search_natural_language():
    """Natural-language questions should be converted to keyword patterns."""
    from library_search import _extract_search_pattern
    pattern = _extract_search_pattern("What is the plugin architecture?")
    # Should NOT contain the raw question or '?'
    assert "?" not in pattern
    assert "what" not in pattern.lower().split("|")
    # Should contain meaningful keywords
    assert "plugin" in pattern.lower()
    assert "architecture" in pattern.lower()
    assert "|" in pattern  # OR pattern


# Test 12: Edge cases for keyword extraction
def test_search_pattern_edge_cases():
    """Edge cases: all stopwords, short words, empty query."""
    from library_search import _extract_search_pattern
    # All stopwords — falls back to escaped query
    pattern = _extract_search_pattern("is it a")
    assert len(pattern) > 0

    # Single keyword survives
    pattern = _extract_search_pattern("What about diarization?")
    assert "diarization" in pattern.lower()

    # Empty-ish query
    pattern = _extract_search_pattern("")
    assert len(pattern) >= 0  # should not crash


# --- Diarization Tests ---

# Test 13: Transcript entry stores speaker field
def test_transcript_entry_with_speaker():
    """Entries with a speaker should include the speaker field."""
    from transcript_mgr import TranscriptManager
    mgr = TranscriptManager(library_path="/tmp/test-diarization")
    mgr.add_entry(start_ms=0, end_ms=5000, text="Hello world", speaker=0)
    entries = mgr.get_entries()
    assert entries[0]["speaker"] == 0


# Test 14: Transcript entry without speaker is backward compatible
def test_transcript_entry_without_speaker():
    """Entries without speaker should not have the field."""
    from transcript_mgr import TranscriptManager
    mgr = TranscriptManager(library_path="/tmp/test-diarization")
    mgr.add_entry(start_ms=0, end_ms=5000, text="Hello world")
    entries = mgr.get_entries()
    assert "speaker" not in entries[0]


# Test 15: VTT export with speaker tags
def test_vtt_export_with_speakers():
    """VTT should include <v Speaker N> voice tags when speaker is set."""
    from transcript_mgr import TranscriptManager
    mgr = TranscriptManager(library_path="/tmp/test-diarization")
    mgr.add_entry(start_ms=0, end_ms=5000, text="First line", speaker=0)
    mgr.add_entry(start_ms=5000, end_ms=10000, text="Second line", speaker=1)
    mgr.add_entry(start_ms=10000, end_ms=15000, text="No speaker line")
    vtt = mgr.export_vtt()
    assert "<v Speaker 0>" in vtt
    assert "<v Speaker 1>" in vtt
    assert "No speaker line" in vtt
    # Entry without speaker should NOT have voice tag
    lines = vtt.split("\n")
    no_speaker_line = [l for l in lines if "No speaker line" in l][0]
    assert "<v " not in no_speaker_line


# Test 16: Full text includes speaker labels
def test_full_text_with_speakers():
    """get_full_text() should prefix entries with [Speaker N]: when available."""
    from transcript_mgr import TranscriptManager
    mgr = TranscriptManager(library_path="/tmp/test-diarization")
    mgr.add_entry(start_ms=0, end_ms=5000, text="Hello", speaker=0)
    mgr.add_entry(start_ms=5000, end_ms=10000, text="World")
    text = mgr.get_full_text()
    assert "[Speaker 0]: Hello" in text
    assert "World" in text
    assert "[Speaker" not in text.split("World")[0].split("Hello")[1]  # no label on unlabeled entry


# Test 17: TranscriptionResult carries speaker
def test_transcription_result_speaker():
    """TranscriptionResult should store speaker ID."""
    from transcriber import TranscriptionResult
    tr = TranscriptionResult(text="Test", start=0.0, end=1.0, is_final=True, speaker=2)
    assert tr.speaker == 2
    tr_no = TranscriptionResult(text="Test", start=0.0, end=1.0, is_final=True)
    assert tr_no.speaker is None


# Test 18: Dominant speaker majority vote
def test_dominant_speaker():
    """_dominant_speaker should return the most common speaker ID."""
    from transcriber import _dominant_speaker

    class MockWord:
        def __init__(self, speaker):
            self.speaker = speaker

    words = [MockWord(0), MockWord(1), MockWord(0), MockWord(0), MockWord(1)]
    assert _dominant_speaker(words) == 0

    words = [MockWord(1), MockWord(1), MockWord(0)]
    assert _dominant_speaker(words) == 1

    # No speaker data
    assert _dominant_speaker([]) is None
