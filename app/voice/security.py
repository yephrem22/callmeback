"""Webhook authentication (PLAN.md §12.2 step 2; research R3) and token-free logs (analyze D1).

The signed URL is PUBLIC_BASE_URL + path + query: behind Caddy the app sees http://app:8000/...,
which is not what Twilio signed. No auth token configured → every request is rejected.
TWILIO_VALIDATE_SIGNATURE=0 is honored only with VOICE_MODE=simulated, where no real call can be
confirmed; with VOICE_MODE=twilio the signature is always checked (analyze C1).
"""
from __future__ import annotations

import logging
import re

from fastapi import Request
from twilio.request_validator import RequestValidator

from app import audit, config
from app.voice.tokens import hash_token

log = logging.getLogger("voice.security")
_TWILIO_PATH = re.compile(r"(/twilio/(?:voice|answer|last4|status)/)([^/?\s\"]+)")


def signed_url(request: Request) -> str:
    query = request.url.query
    return config.S.public_base_url + request.url.path + ("?" + query if query else "")


def check(request: Request, form: dict) -> tuple[bool, str]:
    s = config.S
    if not s.twilio_validate_signature:
        if s.voice_mode == "simulated":
            log.warning("TWILIO_VALIDATE_SIGNATURE=0: accepting an unsigned webhook (simulated mode only)")
            return True, "unchecked"
        log.warning("TWILIO_VALIDATE_SIGNATURE=0 is ignored with VOICE_MODE=twilio; checking the signature")
    if not s.twilio_auth_token:
        return False, "no_auth_token"
    ok = RequestValidator(s.twilio_auth_token).validate(
        signed_url(request), form, request.headers.get("X-Twilio-Signature", ""))
    return (True, "ok") if ok else (False, "bad_signature")


def reject(route: str, token: str, reason: str) -> None:
    """Audit a refused webhook. The token itself is never written, only its hash prefix."""
    try:
        audit.append(None, "twilio", "webhook_rejected",
                     {"route": route, "reason": reason, "token_sha8": hash_token(token)[:8]})
    except Exception:  # noqa: BLE001 - a failed audit write must not turn a 403 into a 500
        log.exception("could not audit webhook_rejected")


def redact(text: str) -> str:
    return _TWILIO_PATH.sub(lambda m: f"{m.group(1)}…{hash_token(m.group(2))[:8]}", text)


class TokenRedactor(logging.Filter):
    """Rewrites /twilio/<route>/<token> in access-log records to /twilio/<route>/…<sha8>."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(redact(a) if isinstance(a, str) else a for a in record.args)
        elif isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


def install_access_log_redaction() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, TokenRedactor) for f in logger.filters):
        logger.addFilter(TokenRedactor())


def warn_if_insecure() -> None:
    s = config.S
    if not s.twilio_validate_signature and s.voice_mode == "twilio":
        log.warning("TWILIO_VALIDATE_SIGNATURE=0 is ignored because VOICE_MODE=twilio")
    if s.voice_mode == "twilio" and not s.twilio_auth_token:
        log.warning("VOICE_MODE=twilio without TWILIO_AUTH_TOKEN: every webhook will be rejected")
