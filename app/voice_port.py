"""The pipeline's only door to voice (research R6). Spec 006 owns app/voice/; until its modules
exist these stubs keep the pipeline runnable and fail closed:

- place_call raises, which the pipeline turns into HELD(CALL_FAILED) (retryable);
- cancel_call never raises;
- classify_answer handles keypad digits per PLAN.md §12.4 and returns UNCLEAR for any speech.

With VOICE_MODE=simulated no call is placed at all (PLAN.md §12.6).
"""
from __future__ import annotations

import importlib
import logging
from typing import Literal

from app.verifications import new_token  # noqa: F401  (re-exported for spec 006's routes)

log = logging.getLogger("voice_port")
Label = Literal["YES", "NO", "UNCLEAR"]


def _impl(module: str, name: str):
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError):
        return None


def place_call(verification_id: str, token: str, to_e164: str) -> str:
    real = _impl("app.voice.twilio_client", "place_call")
    if real is None:
        raise RuntimeError("voice not available: spec 006 has not shipped app/voice/twilio_client.py")
    return real(verification_id, token, to_e164)


def cancel_call(call_sid: str) -> None:
    real = _impl("app.voice.twilio_client", "cancel_call")
    if real is None:
        return
    try:
        real(call_sid)
    except Exception:  # noqa: BLE001 - best effort by contract
        log.warning("cancel_call failed for %s", call_sid)


def classify_answer(digits: str | None, speech: str | None) -> Label:
    real = _impl("app.voice.classify", "classify_answer")
    if real is not None:
        return real(digits, speech)
    if digits:
        return {"1": "YES", "2": "NO"}.get(digits, "UNCLEAR")  # type: ignore[return-value]
    return "UNCLEAR"
