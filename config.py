"""Configuration for meeting-ai."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Keys
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

# Paths
LIBRARY_PATH = Path(os.getenv("LIBRARY_PATH", "~/BrainDrive-Library")).expanduser()
TRANSCRIPTS_PATH = LIBRARY_PATH / "transcripts"
TRANSCRIPT_FILE_PATH = Path(os.getenv("TRANSCRIPT_FILE_PATH", "~/meeting-ai/transcript-live.txt")).expanduser()
VTT_OUTPUT_DIR = Path(os.getenv("VTT_OUTPUT_DIR", str(TRANSCRIPTS_PATH)))

# Audio capture
SPEAKER_VOLUME = float(os.getenv("SPEAKER_VOLUME", "1.0"))
MIC_VOLUME = float(os.getenv("MIC_VOLUME", "1.0"))
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
CHUNK_DURATION_MS = 100  # Send audio every 100ms

# Diarization
ENABLE_DIARIZATION = os.getenv("ENABLE_DIARIZATION", "true").lower() in ("true", "1", "yes")
