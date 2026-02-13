"""Twilio call management — outbound call to Zoom via dial-in number."""

from twilio.rest import Client
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, ZOOM_DIAL_IN_NUMBER


def build_twiml(meeting_id: str, ws_url: str, passcode: str = None) -> str:
    """Build TwiML that navigates Zoom IVR and connects a Media Stream.

    Zoom IVR flow (no passcode):
      [wait ~4s for greeting] → [meeting ID] → [#] → [wait ~3s] → [#] (no participant ID)
    Zoom IVR flow (with passcode):
      [wait ~4s for greeting] → [meeting ID] → [#] → [wait ~3s] → [passcode] → [#] → [wait ~3s] → [#] (no participant ID)
    Then connect bidirectional Media Stream.

    Args:
        meeting_id: Zoom meeting ID (digits only, spaces/dashes stripped).
        ws_url: Public WebSocket URL for Twilio to stream audio to.
        passcode: Optional Zoom meeting passcode.
    """
    digits_only = meeting_id.replace(" ", "").replace("-", "")
    # Use separate Play/Pause elements for reliable IVR timing.
    # Zoom IVR prompts take 5-8s to speak — must wait for prompt to finish
    # before sending DTMF, or Zoom won't hear the tones.
    if passcode:
        passcode_digits = passcode.replace(" ", "").replace("-", "")
        # Zoom's passcode prompt ("Your meeting ID has been verified. Please enter
        # the meeting passcode followed by pound.") takes ~9 seconds to speak.
        # Must wait for it to finish before sending DTMF.
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="6"/>
    <Play digits="wwwwwwww{digits_only}#"/>
    <Pause length="14"/>
    <Play digits="{passcode_digits}#"/>
    <Pause length="10"/>
    <Play digits="#"/>
    <Pause length="3"/>
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
</Response>"""
    else:
        dtmf_sequence = f"wwwwwwww{digits_only}#wwwwwwwwww#"
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Pause length="6"/>
    <Play digits="{dtmf_sequence}"/>
    <Pause length="3"/>
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
</Response>"""


def start_call(meeting_id: str, ws_url: str, passcode: str = None) -> str:
    """Initiate an outbound call from Twilio to Zoom's dial-in number.

    Args:
        meeting_id: Zoom meeting ID.
        ws_url: Public WebSocket URL for media streaming.
        passcode: Optional Zoom meeting passcode.

    Returns:
        The Twilio Call SID.
    """
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    twiml = build_twiml(meeting_id, ws_url, passcode=passcode)
    call = client.calls.create(
        twiml=twiml,
        to=ZOOM_DIAL_IN_NUMBER,
        from_=TWILIO_PHONE_NUMBER,
    )
    return call.sid


def end_call(call_sid: str):
    """End an active Twilio call.

    Args:
        call_sid: The SID of the call to terminate.
    """
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.calls(call_sid).update(status="completed")
