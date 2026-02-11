"""FastAPI server — WebSocket transcript streaming, HTTP endpoints, static files."""

import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from audio_capture import start_capture_stream
from transcriber import DeepgramTranscriber, TranscriptionResult
from transcript_mgr import TranscriptManager, auto_process_transcript
from chat_handler import detect_intent, handle_chat_message, NoteManager
from config import HOST, PORT


# --- App state ---

class AppState:
    """Mutable application state shared across endpoints."""

    def __init__(self):
        self.state: str = "idle"  # idle | recording | processing
        self.transcript_mgr = TranscriptManager()
        self.note_mgr = NoteManager()
        self.transcriber: DeepgramTranscriber | None = None
        self.stop_event: asyncio.Event | None = None
        self.capture_task: asyncio.Task | None = None
        self.start_time: float | None = None

    def reset(self):
        self.state = "idle"
        self.transcriber = None
        self.stop_event = None
        self.capture_task = None
        self.start_time = None
        self.note_mgr.clear()

    @property
    def duration_seconds(self) -> float:
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time


app_state = AppState()


# --- FastAPI app ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup on shutdown
    if app_state.stop_event:
        app_state.stop_event.set()
    if app_state.transcriber:
        await app_state.transcriber.close()


app = FastAPI(lifespan=lifespan)

# Serve static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# --- Routes ---

@app.get("/")
async def index():
    """Serve the main UI."""
    return FileResponse(static_dir / "index.html")


@app.get("/api/status")
async def status():
    """Return current app state."""
    return {
        "state": app_state.state,
        "duration": app_state.duration_seconds,
        "entries": app_state.transcript_mgr.entry_count(),
    }


@app.post("/api/start")
async def start():
    """Start audio capture and transcription."""
    if app_state.state == "recording":
        return JSONResponse({"error": "Already recording"}, status_code=409)

    app_state.transcript_mgr.clear()
    app_state.state = "recording"
    app_state.start_time = time.time()
    app_state.stop_event = asyncio.Event()

    # Transcript callback — called by Deepgram for each result
    async def on_transcript(result: TranscriptionResult):
        if result.is_final and result.text:
            app_state.transcript_mgr.add_entry(
                start_ms=int(result.start * 1000),
                end_ms=int(result.end * 1000),
                text=result.text,
                speaker=result.speaker,
            )

    # Connect to Deepgram
    app_state.transcriber = DeepgramTranscriber(on_transcript=on_transcript)
    await app_state.transcriber.connect()

    # Start audio capture → Deepgram pipeline
    async def audio_to_deepgram(audio_bytes: bytes):
        await app_state.transcriber.send_audio(audio_bytes)

    app_state.capture_task = asyncio.create_task(
        start_capture_stream(audio_to_deepgram, app_state.stop_event)
    )

    return {"status": "recording"}


@app.post("/api/stop")
async def stop(request: Request):
    """Stop recording, close connections, export VTT."""
    if app_state.state != "recording":
        return JSONResponse({"error": "Not recording"}, status_code=409)

    # Read optional topic from request body
    topic = "meeting"
    try:
        body = await request.json()
        topic = body.get("topic", "meeting") or "meeting"
    except Exception:
        pass

    app_state.state = "processing"

    # Stop audio capture
    if app_state.stop_event:
        app_state.stop_event.set()

    # Wait for capture task to finish
    if app_state.capture_task:
        try:
            await asyncio.wait_for(app_state.capture_task, timeout=5.0)
        except (asyncio.TimeoutError, Exception):
            app_state.capture_task.cancel()

    # Close Deepgram
    if app_state.transcriber:
        await app_state.transcriber.close()

    # Export VTT if there are entries
    vtt_path = None
    processed_path = None
    if app_state.transcript_mgr.entry_count() > 0:
        vtt_path = app_state.transcript_mgr.save_vtt(meeting_title=topic)
        # Auto-process transcript (extract decisions, tasks, ideas)
        try:
            processed_path = await auto_process_transcript(vtt_path)
        except Exception as e:
            print(f"Auto-processing failed: {e}")

    duration = app_state.duration_seconds
    entries = app_state.transcript_mgr.entry_count()
    app_state.reset()

    return {
        "status": "stopped",
        "duration": duration,
        "entries": entries,
        "vtt_path": vtt_path,
        "processed_path": processed_path,
    }


# --- Chat + Notes ---

@app.post("/api/chat")
async def chat(body: dict):
    """Handle a chat message — question or note."""
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "Empty message"}, status_code=400)

    intent = detect_intent(message)

    if intent == "note":
        note = app_state.note_mgr.capture_note(
            message=message,
            transcript_entries=app_state.transcript_mgr.get_entries(),
            timestamp_ms=int(app_state.duration_seconds * 1000),
        )
        return {"type": "note", "response": f"Noted: {message}", "note": note}

    # Question — Claude searches Library via tool-use loop
    transcript_text = app_state.transcript_mgr.get_full_text()

    response_text = await handle_chat_message(
        message=message,
        transcript_text=transcript_text,
    )

    return {"type": "question", "response": response_text}


@app.get("/api/notes")
async def get_notes():
    """Return all captured action notes."""
    return app_state.note_mgr.get_notes()


# --- WebSocket for live transcript ---

@app.websocket("/ws/transcript")
async def ws_transcript(ws: WebSocket):
    """WebSocket endpoint for live transcript streaming."""
    await ws.accept()
    await app_state.transcript_mgr.register(ws)
    try:
        while True:
            # Keep connection alive, listen for client messages (pings)
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await app_state.transcript_mgr.unregister(ws)


# --- Entry point ---

if __name__ == "__main__":
    import uvicorn
    print(f"Starting meeting-ai server at http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
