"""Placing and cancelling verification calls (PLAN.md §12.1, §7.5).

`to_e164` is always the verification's `phone_called` (the vendor's phone_on_file, or
DEMO_VENDOR_PHONE for change cases), set by pipeline.request_callback; never a number from an
email. A failure to place raises, and the pipeline holds with CALL_FAILED (retryable).
"""
from __future__ import annotations

import logging

from twilio.rest import Client

from app import config

log = logging.getLogger("voice.twilio")


def _client() -> Client:
    return Client(config.S.twilio_account_sid, config.S.twilio_auth_token)   # per call: picks up .env changes


def place_call(verification_id: str, token: str, to_e164: str) -> str:
    S = config.S
    call = _client().calls.create(
        to=to_e164, from_=S.twilio_from_number,
        url=f"{S.public_base_url}/twilio/voice/{token}", method="POST",
        status_callback=f"{S.public_base_url}/twilio/status/{token}",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST",
        timeout=25,                 # seconds to let it ring
    )
    log.info("call placed", extra={"verification_id": verification_id, "call_sid": call.sid})
    return call.sid


def cancel_call(call_sid: str) -> None:
    """Best effort: hang up a call that is still ringing or in progress. Never raises."""
    try:
        _client().calls(call_sid).update(status="completed")
    except Exception:  # noqa: BLE001 - the call may already be over; superseding must not fail
        log.warning("cancel_call failed", extra={"call_sid": call_sid})
