"""Parse an invoice email (PLAN.md §9.1)."""
from __future__ import annotations

import email
import email.policy
import email.utils
import hashlib
import html
import re
from dataclasses import dataclass
from datetime import UTC

MAX_BYTES = 1_048_576
LLM_BODY_CHARS = 8_000

_TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)
_BR = re.compile(r"<\s*(br|/p|/div|/tr|/li)\s*/?>", re.I)


@dataclass
class ParsedEmail:
    from_name: str
    from_email: str
    from_domain: str
    reply_to: str
    reply_to_domain: str
    subject: str
    received_at: str | None
    body_text: str
    raw_sha256: str


def _domain(addr: str) -> str:
    return addr.rsplit("@", 1)[1].lower().strip() if "@" in addr else ""


def _strip_html(markup: str) -> str:
    text = _BR.sub("\n", markup)
    text = _TAGS.sub("", text)
    return html.unescape(text)


def _body(msg) -> str:
    if msg.is_multipart():
        plain = msg.get_body(preferencelist=("plain",))
        if plain is not None:
            return plain.get_content()
        rich = msg.get_body(preferencelist=("html",))
        if rich is not None:
            return _strip_html(rich.get_content())
        return ""
    content = msg.get_content() if msg.get_content_maintype() == "text" else ""
    if msg.get_content_subtype() == "html":
        return _strip_html(content)
    return content


def parse(raw: bytes) -> ParsedEmail:
    if len(raw) > MAX_BYTES:
        raise ValueError("email too large (over 1 MB)")
    try:
        msg = email.message_from_bytes(raw, policy=email.policy.default)
    except Exception as e:  # pragma: no cover - defensive
        raise ValueError("cannot parse email") from e
    from_name, from_email = email.utils.parseaddr(str(msg.get("From", "")))
    if not from_email:
        raise ValueError("cannot parse email: no From address")
    reply_name, reply_to = email.utils.parseaddr(str(msg.get("Reply-To", "")))
    try:
        body = _body(msg)
    except Exception as e:
        raise ValueError("cannot parse email body") from e
    body = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    if not body.strip():
        raise ValueError("cannot parse email: empty body")
    received_at = None
    date_hdr = msg.get("Date")
    if date_hdr:
        try:
            dt = email.utils.parsedate_to_datetime(str(date_hdr))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            received_at = dt.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        except (TypeError, ValueError):
            received_at = None
    return ParsedEmail(
        from_name=from_name.strip(),
        from_email=from_email.strip().lower(),
        from_domain=_domain(from_email),
        reply_to=reply_to.strip().lower(),
        reply_to_domain=_domain(reply_to),
        subject=str(msg.get("Subject", "")).strip(),
        received_at=received_at,
        body_text=body,
        raw_sha256=hashlib.sha256(raw).hexdigest(),
    )


def body_for_llm(text: str) -> str:
    """The body as the Intake agent sees it: truncated to 8,000 characters."""
    return text[:LLM_BODY_CHARS]
