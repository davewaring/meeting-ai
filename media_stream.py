"""WebSocket server for Twilio Media Streams — receive and send audio."""

import asyncio
import base64
import json
import websockets
from config import WS_HOST, WS_PORT


class MediaStreamServer:
    """Handles the Twilio bidirectional Media Stream over WebSocket.

    Receives mulaw 8kHz audio from Twilio, forwards decoded bytes to a callback.
    Provides send_audio() to inject audio back into the call.
    """

    def __init__(self, on_audio: callable = None, on_connected: callable = None):
        """
        Args:
            on_audio: async callback(audio_bytes: bytes) for each received audio chunk.
            on_connected: async callback() when the media stream connects.
        """
        self.on_audio = on_audio
        self.on_connected = on_connected
        self._ws = None
        self._server = None
        self._stream_sid = None
        self._connected = asyncio.Event()

    async def start(self, host: str = None, port: int = None):
        """Start the WebSocket server."""
        host = host or WS_HOST
        port = port or WS_PORT
        self._server = await websockets.serve(self._handler, host, port)
        print(f"WebSocket server listening on {host}:{port}")

    async def _handler(self, websocket, path=None):
        """Handle a single Twilio WebSocket connection."""
        self._ws = websocket
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                event = message.get("event")

                if event == "connected":
                    print("Twilio Media Stream: connected")

                elif event == "start":
                    self._stream_sid = message.get("streamSid")
                    print(f"Twilio Media Stream: started (streamSid={self._stream_sid})")
                    self._connected.set()
                    if self.on_connected:
                        if asyncio.iscoroutinefunction(self.on_connected):
                            await self.on_connected()
                        else:
                            self.on_connected()

                elif event == "media":
                    media = message.get("media", {})
                    # With both_tracks, only forward inbound audio to transcription
                    track = media.get("track", "inbound")
                    if track == "outbound":
                        continue
                    payload = media.get("payload", "")
                    if payload and self.on_audio:
                        audio_bytes = base64.b64decode(payload)
                        if asyncio.iscoroutinefunction(self.on_audio):
                            await self.on_audio(audio_bytes)
                        else:
                            self.on_audio(audio_bytes)

                elif event == "stop":
                    print("Twilio Media Stream: stopped")
                    break

        except websockets.exceptions.ConnectionClosed:
            print("Twilio Media Stream: connection closed")
        finally:
            self._ws = None
            self._connected.clear()

    async def send_audio(self, audio_bytes: bytes):
        """Send audio back into the Twilio call (mulaw 8kHz, base64).

        Args:
            audio_bytes: Raw mulaw audio bytes to play in the call.
        """
        if self._ws is None or self._stream_sid is None:
            return
        payload = base64.b64encode(audio_bytes).decode("ascii")
        message = json.dumps({
            "event": "media",
            "streamSid": self._stream_sid,
            "media": {
                "payload": payload,
            },
        })
        await self._ws.send(message)

    async def clear_audio(self):
        """Clear any queued audio on the Twilio side."""
        if self._ws is None or self._stream_sid is None:
            return
        message = json.dumps({
            "event": "clear",
            "streamSid": self._stream_sid,
        })
        await self._ws.send(message)

    async def wait_for_connection(self, timeout: float = 60):
        """Wait until the Twilio Media Stream connects.

        Args:
            timeout: Max seconds to wait.
        Raises:
            TimeoutError if connection doesn't arrive.
        """
        await asyncio.wait_for(self._connected.wait(), timeout=timeout)

    async def close(self):
        """Shut down the WebSocket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._ws = None
        print("WebSocket server closed.")

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._connected.is_set()

    @property
    def stream_sid(self) -> str | None:
        return self._stream_sid
