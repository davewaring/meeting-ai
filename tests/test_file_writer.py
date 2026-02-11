"""Tests for file_writer.py — transcript file format, flush, overwrite."""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_file_writer_format_with_speaker():
    """Lines should be formatted as [HH:MM:SS] Speaker N: text."""
    from file_writer import FileWriter
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name
    try:
        writer = FileWriter(path)
        writer.start()
        writer.write_line("Hello world", speaker=0, elapsed_seconds=83)  # 00:01:23
        writer.close()
        content = open(path).read()
        assert content == "[00:01:23] Speaker 0: Hello world\n"
    finally:
        os.unlink(path)


def test_file_writer_format_without_speaker():
    """Lines without speaker should omit the speaker label."""
    from file_writer import FileWriter
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name
    try:
        writer = FileWriter(path)
        writer.start()
        writer.write_line("Hello world", elapsed_seconds=0)
        writer.close()
        content = open(path).read()
        assert content == "[00:00:00] Hello world\n"
    finally:
        os.unlink(path)


def test_file_writer_overwrite_on_start():
    """Starting a new meeting should overwrite the previous transcript."""
    from file_writer import FileWriter
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name
    try:
        writer = FileWriter(path)
        writer.start()
        writer.write_line("Old content", elapsed_seconds=0)
        writer.close()

        # Start again — should overwrite
        writer2 = FileWriter(path)
        writer2.start()
        writer2.write_line("New content", elapsed_seconds=0)
        writer2.close()

        content = open(path).read()
        assert "Old content" not in content
        assert "New content" in content
    finally:
        os.unlink(path)


def test_file_writer_flush_immediate():
    """Content should be readable immediately after write (no buffering)."""
    from file_writer import FileWriter
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name
    try:
        writer = FileWriter(path)
        writer.start()
        writer.write_line("First line", elapsed_seconds=0)
        # Read while file is still open
        content = open(path).read()
        assert "First line" in content, "Content not flushed immediately"
        writer.close()
    finally:
        os.unlink(path)


def test_file_writer_multiple_lines():
    """Multiple lines should append in order with correct timestamps."""
    from file_writer import FileWriter
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        path = f.name
    try:
        writer = FileWriter(path)
        writer.start()
        writer.write_line("First", speaker=0, elapsed_seconds=0)
        writer.write_line("Second", speaker=1, elapsed_seconds=5)
        writer.write_line("Third", elapsed_seconds=3661)  # 01:01:01
        writer.close()

        lines = open(path).readlines()
        assert len(lines) == 3
        assert lines[0] == "[00:00:00] Speaker 0: First\n"
        assert lines[1] == "[00:00:05] Speaker 1: Second\n"
        assert lines[2] == "[01:01:01] Third\n"
    finally:
        os.unlink(path)


def test_format_elapsed():
    """_format_elapsed produces correct HH:MM:SS strings."""
    from file_writer import _format_elapsed
    assert _format_elapsed(0) == "00:00:00"
    assert _format_elapsed(5) == "00:00:05"
    assert _format_elapsed(65) == "00:01:05"
    assert _format_elapsed(3661) == "01:01:01"
    assert _format_elapsed(3599.9) == "00:59:59"
