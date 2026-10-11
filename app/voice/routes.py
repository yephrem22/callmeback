"""The four Twilio webhooks (PLAN.md §12.2, §12.3; contracts/twilio-routes.md).

Each route is async only to read the form and check the signature; every database and pipeline
call runs in one `run_in_threadpool` hop. No route ever calls a language model: the Verifier is
started in the background by the pipeline. The §12.5 decisions live in app/pipeline.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from app import pipeline
from app.voice import security, tokens, twiml

router = APIRouter(prefix="/twilio")
XML = "application/xml"


def _xml(text: str) -> Response:
    return Response(content=text, media_type=XML)


async def _form(request: Request, route: str, token: str) -> tuple[dict | None, Response | None]:
    form = {k: v for k, v in (await request.form()).items() if isinstance(v, str)}
    ok, reason = security.check(request, form)
    if not ok:
        await run_in_threadpool(security.reject, route, token, reason)
        return None, Response(status_code=403)
    return form, None


def _resolve(token: str, form: dict) -> tuple[dict | None, str]:
    ver, state = tokens.lookup(token)
    if state != "expired" and not tokens.match_call(ver, form.get("CallSid")):
        return ver, "expired"                         # another call's webhook: never act on it
    return ver, state


# ---- handlers (threadpool) --------------------------------------------------------

def _voice(token: str, form: dict) -> str:
    ver, state = _resolve(token, form)
    if state == "expired":
        return twiml.expired()
    ctx = pipeline.get_call_context(ver["id"])
    if state == "final":
        return twiml.for_final(ver["final_label"], ctx)
    pipeline.on_call_status(ver["id"], "in-progress")  # the "Answered" event (research R5)
    return twiml.voice_prompt(ctx, token)


def _answer(token: str, form: dict, attempt: str | None) -> str:
    ver, state = _resolve(token, form)
    if state == "expired":
        return twiml.expired()
    ctx = pipeline.get_call_context(ver["id"])
    if state == "final":
        return twiml.for_final(ver["final_label"], ctx)
    return twiml.for_last4("NO_INPUT")                # wired to the pipeline in phase 3 (T011)


def _last4(token: str, form: dict) -> str:
    ver, state = _resolve(token, form)
    if state == "expired":
        return twiml.expired()
    if state == "final":
        return twiml.for_final(ver["final_label"], pipeline.get_call_context(ver["id"]))
    return twiml.for_last4("NO_INPUT")                # wired to the pipeline in phase 3 (T011)


def _status(token: str, form: dict) -> None:
    ver, state = _resolve(token, form)
    if state == "active":
        pipeline.on_call_status(ver["id"], form.get("CallStatus", ""))


# ---- routes -----------------------------------------------------------------------

@router.post("/voice/{token}")
async def voice(request: Request, token: str) -> Response:
    form, denied = await _form(request, "voice", token)
    return denied or _xml(await run_in_threadpool(_voice, token, form))


@router.post("/answer/{token}")
async def answer(request: Request, token: str, n: str | None = None) -> Response:
    form, denied = await _form(request, "answer", token)
    return denied or _xml(await run_in_threadpool(_answer, token, form, n))


@router.post("/last4/{token}")
async def last4(request: Request, token: str) -> Response:
    form, denied = await _form(request, "last4", token)
    return denied or _xml(await run_in_threadpool(_last4, token, form))


@router.post("/status/{token}")
async def status(request: Request, token: str) -> Response:
    form, denied = await _form(request, "status", token)
    if denied:
        return denied
    await run_in_threadpool(_status, token, form)
    return Response(status_code=204)
