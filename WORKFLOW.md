# Meeting AI V2 -- Workflow Guide

Quick reference for using real-time meeting transcription with Claude Code.

---

## Two Modes

| Mode | Entry Point | Audio Source | Requires |
|------|-------------|-------------|----------|
| **Phone-in (recommended)** | `plus_one.py` | Twilio calls Zoom | Twilio account, ngrok |
| **Local capture (fallback)** | `meeting.py` | BlackHole virtual audio | BlackHole 2ch, Multi-Output Device |

Phone-in mode is simpler: one command, no audio routing, and +1 shows up as a real Zoom participant.

---

## Phone-In Mode (Recommended)

### Setup (One-Time)

#### 1. Twilio Account

1. Create an account at [twilio.com](https://www.twilio.com).
2. Get a phone number (US local, ~$1.15/month).
3. Note your Account SID, Auth Token, and phone number.

#### 2. ngrok

Install ngrok (provides public URL for Twilio to reach your WebSocket):

```bash
brew install ngrok
```

Sign up for a free account at [ngrok.com](https://ngrok.com) and configure:

```bash
ngrok config add-authtoken YOUR_TOKEN
```

#### 3. Environment Variables

Create `~/meeting-ai/.env`:

```bash
# Required
DEEPGRAM_API_KEY=your-deepgram-key
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx

# Optional (defaults shown)
ANTHROPIC_API_KEY=your-anthropic-key    # Required for monitor mode
ZOOM_DIAL_IN_NUMBER=+16465588656        # US Zoom dial-in
LIBRARY_PATH=~/BrainDrive-Library
MONITOR_MODEL=claude-sonnet-4-5-20250929
MONITOR_COOLDOWN=45
```

#### 4. Python Dependencies

```bash
cd ~/meeting-ai
.venv/bin/pip install -e .
```

### Starting a Meeting

Open **two terminal tabs**.

**Tab 1 -- +1:**

```bash
cd ~/meeting-ai && .venv/bin/python plus_one.py --meeting-id "123 456 7890" --topic "team-call"
```

Wait for:
```
Connected! +1 is in the meeting.
Monitoring transcript with claude-sonnet-4-5...
```

**Tab 2 -- Claude Code:**

```bash
cd ~/BrainDrive-Library && claude
```

### CLI Options

```bash
# Listen-only (no monitor, just transcription)
python plus_one.py --meeting-id "123 456 7890" --listen-only

# Custom model and cooldown
python plus_one.py --meeting-id "123 456 7890" --model claude-sonnet-4-5-20250929 --cooldown 60

# Verbose (show token usage and timing)
python plus_one.py --meeting-id "123 456 7890" --verbose
```

### What +1 Does

While in the meeting, +1:
- **Transcribes** everything said → `transcript-live.txt`
- **Monitors** the transcript with Claude API, surfacing:
  - Related past decisions and context from the BrainDrive Library
  - Potential conflicts with existing decisions
  - Questions, ideas, and tasks
- **Suggestions** appear in your terminal, color-coded by type

### Costs Per Meeting (~90 min)

| Service | Cost |
|---------|------|
| Twilio voice | ~$1.26 |
| Deepgram | ~$0.39 |
| Claude API (monitor) | ~$5.00 |
| **Total** | **~$6.65** |

---

## Local Capture Mode (Fallback)

Use this when Twilio isn't available or for testing.

### Setup (One-Time)

#### 1. Install BlackHole 2ch

```bash
brew install blackhole-2ch
```

#### 2. Configure Multi-Output Device

Open **Audio MIDI Setup** (Spotlight: "Audio MIDI Setup"):

1. Click the **+** button at bottom-left, select **Create Multi-Output Device**.
2. Check both your normal speakers/headphones **and** BlackHole 2ch.
3. Make sure your speakers/headphones are listed **first** (drag to reorder if needed).
4. Enable **Drift Correction** on BlackHole 2ch.

Before each meeting, set your Mac's **Sound Output** to this Multi-Output Device.

#### 3. Configure Zoom Audio

In Zoom Settings > Audio:
- Set **Speaker** to your Multi-Output Device.
- Set **Microphone** to your normal mic.

### Starting a Meeting (Local Mode)

**Tab 1 -- Transcription:**

```bash
cd ~/meeting-ai && .venv/bin/python meeting.py --topic "topic name"
```

**Tab 2 -- Claude Code:**

```bash
cd ~/BrainDrive-Library && claude
```

---

## During the Meeting -- Using Claude Code

### Prime Context

```
Read ~/meeting-ai/transcript-live.txt
```

### Ask Questions

```
Read ~/meeting-ai/transcript-live.txt -- what's on our agenda today?
Read ~/meeting-ai/transcript-live.txt -- summarize the last 10 minutes
Does what we just discussed conflict with any existing decisions?
```

### Draft Edits

```
Draft the spec updates from what we just discussed
Update decisions.md with what we just agreed on
```

### Tips

- Use `/compact` if context gets full during long meetings.
- The transcript file updates in real time — re-read it whenever you need.
- Format: `[HH:MM:SS] Speaker N: text`

---

## Ending a Meeting

1. Press **Ctrl+C** in the transcription terminal (Tab 1).
2. The VTT file path is printed:
   ```
   VTT saved: /path/to/transcripts/2026-02/2026-02-12_14-30_topic-name.vtt
   ```
3. In Claude Code (Tab 2), run:
   ```
   /transcript /path/to/the/file.vtt
   ```
4. The `/transcript` skill extracts decisions, tasks, and ideas into the Library.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `DEEPGRAM_API_KEY` | *(required)* | API key from console.deepgram.com |
| `TWILIO_ACCOUNT_SID` | *(required for phone-in)* | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | *(required for phone-in)* | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | *(required for phone-in)* | Your Twilio phone number |
| `ZOOM_DIAL_IN_NUMBER` | `+16465588656` | Zoom dial-in number (US) |
| `ANTHROPIC_API_KEY` | *(required for monitor)* | Anthropic API key |
| `LIBRARY_PATH` | `~/BrainDrive-Library` | Path to BrainDrive Library repo |
| `TRANSCRIPT_FILE_PATH` | `~/meeting-ai/transcript-live.txt` | Where the live transcript is written |
| `VTT_OUTPUT_DIR` | `$LIBRARY_PATH/transcripts` | Where VTT files are saved on meeting end |
| `MONITOR_MODEL` | `claude-sonnet-4-5-20250929` | Claude model for monitor analysis |
| `MONITOR_COOLDOWN` | `45` | Seconds between monitor analyses |
| `MONITOR_MIN_NEW_LINES` | `5` | Minimum new lines before triggering analysis |
| `WS_HOST` | `0.0.0.0` | WebSocket server bind address |
| `WS_PORT` | `8765` | WebSocket server port |
| `SPEAKER_VOLUME` | `1.0` | Volume multiplier (local mode only) |
| `MIC_VOLUME` | `1.0` | Mic volume multiplier (local mode only) |
| `ENABLE_DIARIZATION` | `true` | Enable speaker diarization |
| `TTS_PROVIDER` | `twilio` | TTS provider (future: elevenlabs, openai) |
| `TTS_VOICE` | `Polly.Joanna` | TTS voice name |

---

## Troubleshooting

### Phone-In Mode

**Call doesn't connect:**
- Check Twilio Account SID and Auth Token in `.env`.
- Verify your Twilio phone number is active.
- Check ngrok is running (it starts automatically, but may need auth token).

**No transcription:**
- Verify `DEEPGRAM_API_KEY` is set.
- Check the terminal for Deepgram connection errors.
- The audio is mulaw 8kHz — Deepgram handles this natively.

**Monitor not showing suggestions:**
- Set `ANTHROPIC_API_KEY` in `.env`.
- Use `--verbose` to see when analysis runs.
- Cooldown is 45s by default — wait for enough new transcript lines.

**ngrok errors:**
- Run `ngrok config add-authtoken YOUR_TOKEN` if you see auth errors.
- Free tier gives random URLs each time — this is fine for dev.

### Local Mode

**No audio captured:**
- Verify Mac Sound Output is set to the Multi-Output Device.
- In Zoom, check Speaker is set to the Multi-Output Device.
- Run `python audio_capture.py` to test capture.

**Volume too low/high:**
- Adjust `SPEAKER_VOLUME` and `MIC_VOLUME` in `.env`.
