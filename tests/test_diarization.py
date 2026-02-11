"""Diarization tests: speaker identification in transcription results."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_transcription_result_speaker():
    """TranscriptionResult should store speaker ID."""
    from transcriber import TranscriptionResult
    tr = TranscriptionResult(text="Test", start=0.0, end=1.0, is_final=True, speaker=2)
    assert tr.speaker == 2
    tr_no = TranscriptionResult(text="Test", start=0.0, end=1.0, is_final=True)
    assert tr_no.speaker is None


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
