"""Configuration for meeting-ai."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Keys
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Paths
LIBRARY_PATH = Path(os.getenv("LIBRARY_PATH", "~/BrainDrive-Library")).expanduser()
TRANSCRIPTS_PATH = LIBRARY_PATH / "transcripts"

# Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8910"))

# Audio capture
SPEAKER_VOLUME = float(os.getenv("SPEAKER_VOLUME", "1.0"))
MIC_VOLUME = float(os.getenv("MIC_VOLUME", "1.0"))
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
CHUNK_DURATION_MS = 100  # Send audio every 100ms

# AI
AI_MODEL = os.getenv("AI_MODEL", "claude-sonnet-4-5-20250929")
