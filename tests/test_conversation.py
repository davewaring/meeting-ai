"""Tests for conversation.py — wake word detection, question extraction, tool execution."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Wake word detection ---

def test_wake_word_plus_one():
    """Should detect 'plus one' as a wake word."""
    from conversation import has_wake_word
    assert has_wake_word("Hey plus one, what's our status?")


def test_wake_word_plus_1():
    """Should detect '+1' as a wake word."""
    from conversation import has_wake_word
    assert has_wake_word("Hey +1, check the build plan")


def test_wake_word_hey_plus_one():
    """Should detect 'hey plus one' as a wake word."""
    from conversation import has_wake_word
    assert has_wake_word("hey plus one can you look that up")


def test_wake_word_case_insensitive():
    """Wake word detection should be case-insensitive."""
    from conversation import has_wake_word
    assert has_wake_word("PLUS ONE what do you think?")
    assert has_wake_word("Plus One, check the decisions")


def test_no_wake_word():
    """Should not trigger on random text."""
    from conversation import has_wake_word
    assert not has_wake_word("Let's discuss the timeline")
    assert not has_wake_word("We need one more feature")


def test_wake_word_in_context():
    """Should detect wake word mid-sentence."""
    from conversation import has_wake_word
    assert has_wake_word("so plus one can you check that?")


# --- Question extraction ---

def test_extract_question_after_plus_one():
    """Should extract text after 'plus one'."""
    from conversation import extract_question
    q = extract_question("plus one, what's the status of braindrive-code?")
    assert "status" in q
    assert "plus one" not in q.lower()


def test_extract_question_after_plus_1():
    """Should extract text after '+1'."""
    from conversation import extract_question
    q = extract_question("+1 check the build plan for hardware")
    assert "build plan" in q


def test_extract_question_strips_punctuation():
    """Should strip leading commas and whitespace from extracted question."""
    from conversation import extract_question
    q = extract_question("plus one,   what decisions have we made?")
    assert q.startswith("what")


def test_extract_question_no_wake_word():
    """If no wake word, return the full text."""
    from conversation import extract_question
    text = "what's the status of the project?"
    assert extract_question(text) == text


# --- Tool execution ---

def test_read_file_not_found():
    """read_file should return error message for missing file."""
    from conversation import _execute_read_file
    result = _execute_read_file("/nonexistent/path/12345/foo.md")
    assert "not found" in result.lower() or "error" in result.lower()


def test_read_file_is_directory():
    """read_file should indicate when path is a directory."""
    from conversation import _execute_read_file
    result = _execute_read_file("")  # Will try to read Library root
    assert "directory" in result.lower() or "not found" in result.lower()


def test_list_directory_nonexistent():
    """list_directory should handle missing directories."""
    from conversation import _execute_list_directory
    result = _execute_list_directory("/nonexistent/path/12345")
    assert "not found" in result.lower()


def test_search_files_nonexistent_dir():
    """search_files should handle missing directories."""
    from conversation import _execute_search_files
    result = _execute_search_files("test", "/nonexistent/path/12345")
    assert "not found" in result.lower()


def test_execute_tool_unknown():
    """Unknown tool should return error."""
    from conversation import _execute_tool
    result = _execute_tool("unknown_tool", {})
    assert "unknown" in result.lower()


def test_execute_tool_dispatch():
    """_execute_tool should dispatch to the correct function."""
    from conversation import _execute_tool
    # read_file with nonexistent path
    result = _execute_tool("read_file", {"path": "/nonexistent/12345.md"})
    assert "not found" in result.lower()


# --- Tool definitions ---

def test_tools_have_required_fields():
    """All tools should have name, description, and input_schema."""
    from conversation import TOOLS
    for tool in TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool


def test_tools_count():
    """Should have exactly 3 tools: read_file, search_files, list_directory."""
    from conversation import TOOLS
    names = [t["name"] for t in TOOLS]
    assert "read_file" in names
    assert "search_files" in names
    assert "list_directory" in names
    assert len(TOOLS) == 3
