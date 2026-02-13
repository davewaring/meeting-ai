"""Configuration for meeting-ai."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Keys
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Twilio
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
ZOOM_DIAL_IN_NUMBER = os.getenv("ZOOM_DIAL_IN_NUMBER", "+16465588656")

# Paths
LIBRARY_PATH = Path(os.getenv("LIBRARY_PATH", "~/BrainDrive-Library")).expanduser()
TRANSCRIPTS_PATH = LIBRARY_PATH / "transcripts"
TRANSCRIPT_FILE_PATH = Path(os.getenv("TRANSCRIPT_FILE_PATH", "~/meeting-ai/transcript-live.txt")).expanduser()
VTT_OUTPUT_DIR = Path(os.getenv("VTT_OUTPUT_DIR", str(TRANSCRIPTS_PATH)))

# Audio capture (BlackHole local mode)
SPEAKER_VOLUME = float(os.getenv("SPEAKER_VOLUME", "1.0"))
MIC_VOLUME = float(os.getenv("MIC_VOLUME", "1.0"))
SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
CHUNK_DURATION_MS = 100  # Send audio every 100ms

# Twilio audio (phone mode)
TWILIO_SAMPLE_RATE = 8000
TWILIO_ENCODING = "mulaw"

# WebSocket server for Twilio Media Streams
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", "8765"))

# Diarization
ENABLE_DIARIZATION = os.getenv("ENABLE_DIARIZATION", "true").lower() in ("true", "1", "yes")

# Monitor
MONITOR_MODEL = os.getenv("MONITOR_MODEL", "claude-sonnet-4-5-20250929")
MONITOR_COOLDOWN = int(os.getenv("MONITOR_COOLDOWN", "45"))
MONITOR_MIN_NEW_LINES = int(os.getenv("MONITOR_MIN_NEW_LINES", "5"))

# TTS
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai")
TTS_VOICE = os.getenv("TTS_VOICE", "nova")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
