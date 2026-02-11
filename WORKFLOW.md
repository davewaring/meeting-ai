# Meeting AI V2 -- Workflow Guide

Quick reference for using real-time meeting transcription with Claude Code.

---

## Setup (One-Time)

### 1. Install BlackHole 2ch

```bash
brew install blackhole-2ch
```

### 2. Configure Multi-Output Device

Open **Audio MIDI Setup** (Spotlight: "Audio MIDI Setup"):

1. Click the **+** button at bottom-left, select **Create Multi-Output Device**.
2. Check both your normal speakers/headphones **and** BlackHole 2ch.
3. Make sure your speakers/headphones are listed **first** (drag to reorder if needed). This is the device you hear through.
4. Enable **Drift Correction** on BlackHole 2ch (check the box in the right column).

Before each meeting, set your Mac's **Sound Output** to this Multi-Output Device. This routes audio to both your ears and BlackHole for capture.

### 3. Configure Zoom Audio

In Zoom Settings > Audio:
- Set **Speaker** to your Multi-Output Device (so meeting audio flows through BlackHole).
- Set **Microphone** to your normal mic (MacBook mic or external).

### 4. Environment Variables

Create `~/meeting-ai/.env`:

```bash
# Required
DEEPGRAM_API_KEY=your-key-here

# Optional (defaults shown)
LIBRARY_PATH=~/BrainDrive-Library
TRANSCRIPT_FILE_PATH=~/meeting-ai/transcript-live.txt
VTT_OUTPUT_DIR=~/BrainDrive-Library/transcripts
SPEAKER_VOLUME=1.0
MIC_VOLUME=1.0
ENABLE_DIARIZATION=true
```

### 5. Python Virtual Environment

```bash
cd ~/meeting-ai
python3 -m venv .venv
.venv/bin/pip install -e .
```

---

## Starting a Meeting

Open **two terminal tabs**.

**Tab 1 -- Transcription:**

```bash
cd ~/meeting-ai && .venv/bin/python meeting.py --topic "topic name"
```

Wait for both confirmation messages:
```
Meeting started. Transcript: /Users/davidwaring/meeting-ai/transcript-live.txt
Starting audio capture from: BlackHole 2ch
Deepgram connected and ready.
Press Ctrl+C to stop.
```

**Tab 2 -- Claude Code:**

```bash
cd ~/BrainDrive-Library && claude
```

---

## During the Meeting -- Using Claude Code

### Prime Context

At the start of the meeting, give Claude Code the live transcript and any relevant project context:

```
Read ~/meeting-ai/transcript-live.txt
```

```
We're about to discuss BrainDrive Code -- review the project folder
```

### Ask Questions from the Transcript

Re-read the transcript at any point to catch up on what was said:

```
Read ~/meeting-ai/transcript-live.txt -- what's on our agenda today?
```

```
Read ~/meeting-ai/transcript-live.txt -- what did we just discuss about the API?
```

```
Read ~/meeting-ai/transcript-live.txt -- summarize the last 10 minutes
```

### Ask Questions from the Library

Claude Code can cross-reference the transcript against the full BrainDrive Library:

```
What did we decide about authentication in our last meeting?
```

```
What's the current status of the BrainDrive Code project?
```

```
Does what we just discussed conflict with any existing decisions?
```

### Draft Edits in Real Time

Ask Claude Code to prepare document updates based on the live discussion:

```
Draft the spec updates from what we just discussed about the plugin API
```

```
Update decisions.md with what we just agreed on about the deployment strategy
```

```
Add that idea about caching to the ideas.md file
```

### Tips

- Use `/compact` if context gets full during long meetings.
- You can re-read the transcript as many times as needed -- it updates in real time.
- The transcript file is plain text with timestamps: `[HH:MM:SS] Speaker N: text`

---

## Ending a Meeting

1. Press **Ctrl+C** in the transcription terminal (Tab 1).
2. The VTT file path is printed:
   ```
   VTT saved: /Users/davidwaring/BrainDrive-Library/transcripts/2026-02/2026-02-11_14-30_topic-name.vtt
   ```
3. In Claude Code (Tab 2), run:
   ```
   /transcript /Users/davidwaring/BrainDrive-Library/transcripts/2026-02/2026-02-11_14-30_topic-name.vtt
   ```
4. The `/transcript` skill walks through extraction of decisions, tasks, and ideas into the Library.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DEEPGRAM_API_KEY` | *(required)* | API key from console.deepgram.com |
| `LIBRARY_PATH` | `~/BrainDrive-Library` | Path to BrainDrive Library repo |
| `TRANSCRIPT_FILE_PATH` | `~/meeting-ai/transcript-live.txt` | Where the live transcript is written during meetings |
| `VTT_OUTPUT_DIR` | `$LIBRARY_PATH/transcripts` | Where VTT files are saved on meeting end |
| `SPEAKER_VOLUME` | `1.0` | Volume multiplier for speaker audio (BlackHole). Increase if other participants are too quiet. |
| `MIC_VOLUME` | `1.0` | Volume multiplier for your microphone. Increase if your voice is too quiet. |
| `ENABLE_DIARIZATION` | `true` | Enable Deepgram speaker diarization (labels speakers as Speaker 0, Speaker 1, etc.) |
| `SAMPLE_RATE` | `16000` | Audio sample rate in Hz (hardcoded in config.py, not configurable via .env) |
| `CHANNELS` | `1` | Audio channels (hardcoded, mono) |
| `CHUNK_DURATION_MS` | `100` | Audio chunk size sent to Deepgram in milliseconds (hardcoded) |

---

## Troubleshooting

**No audio captured / transcript is empty:**
- Verify Mac Sound Output is set to the Multi-Output Device (not just your speakers).
- In Zoom, check that the Speaker is set to the Multi-Output Device.
- Run `python audio_capture.py` in the meeting-ai directory to list devices and test capture.
- Make sure BlackHole 2ch appears in the device list.

**Volume too low / too high:**
- Adjust `SPEAKER_VOLUME` and `MIC_VOLUME` in `.env` (values above 1.0 amplify, below 1.0 reduce).
- If peak audio is near 0, the audio routing is likely wrong (check Multi-Output Device setup).

**No transcript appearing (audio works but no text):**
- Check that `DEEPGRAM_API_KEY` is set correctly in `.env`.
- Check your network connection -- Deepgram requires internet access.
- Look for "Deepgram connected and ready." in the terminal output. If missing, the connection failed.

**Deepgram errors in terminal:**
- `401 / Unauthorized`: API key is invalid or expired. Get a new one from console.deepgram.com.
- `WebSocket closed`: Network interruption. Restart `meeting.py`.
- `recv error`: Usually a transient network issue. Restart the meeting.

**BlackHole not found:**
- Install with `brew install blackhole-2ch` and restart Audio MIDI Setup.
- If installed but not showing, try rebooting.

**Microphone not detected:**
- The system uses your default input device (excluding BlackHole).
- If no mic is found, it falls back to speaker-only capture (you won't be transcribed).
- Check System Settings > Sound > Input to verify your mic is recognized.
