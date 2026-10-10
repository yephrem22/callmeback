"""Throwaway Twilio spike for milestone B2 (PLAN.md §18, spec 002 FR-017).

Measures dial → ring → answer on the real VM before spec 006 exists. Mounted by
app/main.py only in DEMO_MODE. No signature check on purpose: the routes carry no
state and are removed when spec 006 lands with the real /twilio/* routes (§12).
Every event is one JSON log line so timings can be read from `docker compose logs app`.
"""
from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.config import S

log = logging.getLogger("voice.spike")
router = APIRouter(prefix="/twilio/spike")
VOICE = "Polly.Joanna-Neural"


def _log(event: str, **data) -> None:
    log.info(json.dumps({"ts": round(time.time(), 3), "spike": event, **data}))


def _twiml(vr: VoiceResponse) -> Response:
    return Response(content=str(vr), media_type="application/xml")


@router.post("/voice")
async def voice(request: Request) -> Response:
    form = await request.form()
    _log("voice_fetched", call_sid=form.get("CallSid"), status=form.get("CallStatus"))
    vr = VoiceResponse()
    gather = Gather(input="dtmf speech", num_digits=1, timeout=7, speech_timeout="auto",
                    hints="yes, no, yes we did, no we didn't, that wasn't us, correct",
                    action_on_empty_result=True, language="en-US",
                    action=f"{S.public_base_url}/twilio/spike/answer", method="POST")
    gather.say(f"Hello. This is a test of the accounts payable verification line for {S.payer_name}. "
               "If you can hear this clearly, say yes or press 1.", voice=VOICE)
    vr.append(gather)
    return _twiml(vr)


@router.post("/answer")
async def answer(request: Request) -> Response:
    form = await request.form()
    _log("answer", call_sid=form.get("CallSid"), digits=form.get("Digits"),
         speech=form.get("SpeechResult"), confidence=form.get("Confidence"))
    vr = VoiceResponse()
    vr.say("Thank you. The test is complete. Goodbye.", voice=VOICE)
    vr.hangup()
    return _twiml(vr)


@router.post("/status")
async def status(request: Request) -> Response:
    form = await request.form()
    _log("status", call_sid=form.get("CallSid"), call_status=form.get("CallStatus"),
         duration=form.get("CallDuration"), sequence=form.get("SequenceNumber"))
    return Response(status_code=204)
