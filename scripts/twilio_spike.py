"""Laptop side of the Twilio spike (milestone B2): place one call to DEMO_VENDOR_PHONE through
the VM's /twilio/spike routes and print the status timeline. Usage: .venv/bin/python scripts/twilio_spike.py
Never dials any other number (constitution IV). Refuses to run against a placeholder PUBLIC_BASE_URL.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import dotenv_values  # noqa: E402

from scripts.check_env import REPO_ROOT, is_placeholder, mask  # noqa: E402


def main() -> int:
    env = {k: (v or "") for k, v in dotenv_values(REPO_ROOT / ".env").items()}
    base = env.get("PUBLIC_BASE_URL", "").rstrip("/")
    to = env.get("DEMO_VENDOR_PHONE", "")
    for key in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"):
        if is_placeholder(env.get(key)):
            print(f"{key} is not set", file=sys.stderr)
            return 1
    if is_placeholder(base) or is_placeholder(to):
        print("PUBLIC_BASE_URL or DEMO_VENDOR_PHONE is a placeholder; nothing dialled", file=sys.stderr)
        return 1

    from twilio.rest import Client
    client = Client(env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"])
    t0 = time.time()
    call = client.calls.create(
        to=to, from_=env["TWILIO_FROM_NUMBER"],
        url=f"{base}/twilio/spike/voice", method="POST",
        status_callback=f"{base}/twilio/spike/status",
        status_callback_event=["initiated", "ringing", "answered", "completed"],
        status_callback_method="POST",
        timeout=25,
    )
    print(f"call {call.sid} placed to {mask(to)} at t=0.0 s; answer the phone and say yes or press 1")
    seen = None
    while True:
        c = client.calls(call.sid).fetch()
        if c.status != seen:
            print(f"  t={time.time() - t0:5.1f} s  status={c.status}")
            seen = c.status
        if c.status in ("completed", "busy", "failed", "no-answer", "canceled"):
            break
        time.sleep(1)
    print(f"final: {c.status}, duration {c.duration}s, answered_by={getattr(c, 'answered_by', None)}")
    print("webhook timings: ssh root@VM 'cd /opt/callmeback && docker compose logs app | grep spike'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
