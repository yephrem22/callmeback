"""Readiness matrix for every integration (PLAN.md §0.4, §0.5, §7.1).

Prints one row per integration as READY / FAKE / MISSING / FAILED with masked
evidence and a next step, and exits 0 or 1 by the phase gate:

  build      (default) fails only on malformed app secrets
  integrate  also requires Akamai inference, the public URL and Twilio READY
  demo       also requires AI_MODE=live, VOICE_MODE=twilio, the /mcp probe,
             the Enterprise-Bench version and a Twilio balance of at least $10

Secrets are never printed beyond their last four characters. No Twilio call
is placed unless --call-test is passed. Contract: specs/001-env-readiness/
contracts/check-env-cli.md. The pure core is `evaluate()`; `run_probes()` is
the only networked function.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_TIMEOUT = 8.0
MASK = "••••"

STATUSES = ("READY", "FAKE", "MISSING", "FAILED")
PHASES = ("build", "integrate", "demo")

# §7.1 example values that do not contain the word "replace".
PLACEHOLDER_VALUES = frozenset({
    "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "172-105-12-34.sslip.io",
    "https://172-105-12-34.sslip.io",
    "team@example.com",
})

SECRET_VARS = (
    "AKAMAI_API_KEY", "LINODE_TOKEN", "TWILIO_AUTH_TOKEN", "OBJ_ACCESS_KEY",
    "OBJ_SECRET_KEY", "MCP_TOKEN", "INTERNAL_TOKEN", "DASH_PASS_HASH",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
)

BCRYPT_RE = re.compile(r"^\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}$")
MIN_TOKEN_LEN = 32
MIN_TWILIO_BALANCE = 10.0
EB_FOLDERS = ("crm_json_data", "pm_json_data", "maple_kb", "transcripts", "internal_docs")


# --------------------------------------------------------------------------- helpers

def mask(value: str | None) -> str:
    """Return the mask plus the last four characters; never more."""
    if not value or len(value) <= 4:
        return MASK
    return MASK + value[-4:]


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    v = value.strip()
    return v == "" or "replace" in v.lower() or v in PLACEHOLDER_VALUES


def scrub(text: str, secrets: Iterable[str]) -> str:
    """Replace every occurrence of a known secret (8+ chars) with its masked form."""
    for s in sorted({s for s in secrets if s and len(s) >= 8}, key=len, reverse=True):
        text = text.replace(s, mask(s))
    return text


def load_env(path: Path | None) -> dict[str, str]:
    """`.env` values (single quotes honoured) overlaid by the process environment."""
    env: dict[str, str] = {}
    if path is not None and path.is_file():
        env.update({k: (v or "") for k, v in dotenv_values(path).items()})
    for key in ALL_VARS:
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _secret_values(env: dict[str, str]) -> list[str]:
    return [env.get(k, "") for k in SECRET_VARS if not is_placeholder(env.get(k))]


# --------------------------------------------------------------------------- model

@dataclass
class ProbeResult:
    ok: bool
    evidence: str = ""
    error: str | None = None
    duration_ms: int = 0


@dataclass
class RowSpec:
    key: str
    name: str
    env: tuple[str, ...]
    required: tuple[str, ...]
    mode_var: str | None = None
    fake_value: str | None = None
    gate: tuple[str, ...] = ()
    next_missing: str = ""
    next_fake: str = ""
    next_failed: str = ""


ROWS: tuple[RowSpec, ...] = (
    RowSpec(
        "akamai_inference", "Akamai inference",
        ("AKAMAI_BASE_URL", "AKAMAI_API_KEY", "MODEL_ID"),
        ("AKAMAI_BASE_URL", "AKAMAI_API_KEY", "MODEL_ID"),
        "AI_MODE", "off", ("integrate", "demo"),
        next_missing="Put the organizers' key in .env (§0.2 T+20)",
        next_fake="Set AI_MODE=live once the key works (§0.4)",
        next_failed="Check AKAMAI_BASE_URL, the key and MODEL_ID with the organizers",
    ),
    RowSpec(
        "akamai_cloud_api", "Akamai Cloud API",
        ("LINODE_TOKEN",), ("LINODE_TOKEN",),
        next_missing="Create a Linode token, laptop only (§0.2 T+25)",
        next_failed="Token rejected; create a new one with the §0.2 T+25 scopes",
    ),
    RowSpec(
        "public_url", "Public HTTPS URL",
        ("HOST", "PUBLIC_BASE_URL", "ACME_EMAIL"), ("HOST", "PUBLIC_BASE_URL"),
        gate=("integrate", "demo"),
        next_missing="Provision the VM (spec 002, §16.1)",
        next_failed="Check Caddy logs and the certificate (§16.5)",
    ),
    RowSpec(
        "object_storage", "Object Storage",
        ("OBJ_ENDPOINT", "OBJ_REGION", "OBJ_BUCKET", "OBJ_ACCESS_KEY", "OBJ_SECRET_KEY"),
        ("OBJ_ENDPOINT", "OBJ_REGION", "OBJ_BUCKET", "OBJ_ACCESS_KEY", "OBJ_SECRET_KEY"),
        "STORAGE_MODE", "local",
        next_missing="Create the bucket and key (§16.3)",
        next_fake="Set STORAGE_MODE=s3 once the bucket works (P1)",
        next_failed="Check the endpoint, bucket name and key scope (§16.3)",
    ),
    RowSpec(
        "twilio", "Twilio",
        ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER", "DEMO_VENDOR_PHONE"),
        ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER"),
        "VOICE_MODE", "simulated", ("integrate", "demo"),
        next_missing="Upgrade Twilio and buy a Voice number (§0.2 T+10)",
        next_fake="Set VOICE_MODE=twilio once Twilio and PUBLIC_BASE_URL are live",
        next_failed="Fix the account (upgrade, top up to $10+, Voice number) (§16.4)",
    ),
    RowSpec(
        "devrev", "DevRev and Enterprise-Bench",
        ("EB_DATA_DIR", "EB_DATASET_VERSION", "MCP_TOKEN", "MCP_ALLOWED_HOSTS", "DEVREV_ORG_URL"),
        ("EB_DATA_DIR", "MCP_TOKEN"),
        "EB_DATASET_VERSION", "public-", ("demo",),
        next_missing="Download the public release; ask the SE for the export (§15.2)",
        next_fake="Switch EB_DATA_DIR and EB_DATASET_VERSION to the SE's pinned export (§15.2)",
        next_failed="Check the data folders, MCP_TOKEN length and the deployed /mcp (§15.2, §16.5)",
    ),
    RowSpec(
        "aws", "AWS (optional)",
        ("LLM_FALLBACK", "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "BEDROCK_MODEL_ID"),
        ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "BEDROCK_MODEL_ID"),
        "LLM_FALLBACK", "none",
        next_missing="Optional: add AWS keys and BEDROCK_MODEL_ID for the Bedrock fallback (§0.4)",
        next_fake="Nothing to do; optional",
        next_failed="Optional: check the AWS keys and Bedrock model access",
    ),
    RowSpec(
        "app_secrets", "App secrets",
        ("INTERNAL_TOKEN", "MCP_TOKEN", "DASH_USER", "DASH_PASS_HASH"),
        ("INTERNAL_TOKEN", "MCP_TOKEN", "DASH_PASS_HASH"),
        gate=("build", "integrate", "demo"),
        next_missing="Run make secrets",
        next_failed="Run make secrets",
    ),
)
ROW_BY_KEY = {r.key: r for r in ROWS}
ALL_VARS = tuple(dict.fromkeys(v for r in ROWS for v in r.env + ((r.mode_var,) if r.mode_var else ())))


@dataclass
class RowReport:
    key: str
    name: str
    status: str
    probe: str
    evidence: str
    next_step: str
    env: list[str]


@dataclass
class Report:
    phase: str
    ok: bool
    failures: list[str]
    generated_at: str
    rows: list[RowReport] = field(default_factory=list)


# --------------------------------------------------------------------------- pure core

def _is_fake(spec: RowSpec, env: dict[str, str]) -> bool:
    if not spec.mode_var:
        return False
    value = (env.get(spec.mode_var) or "").strip()
    if spec.key == "devrev":
        return value.startswith(spec.fake_value or "public-")
    return value == spec.fake_value


def _missing(spec: RowSpec, env: dict[str, str]) -> list[str]:
    if spec.key == "app_secrets":
        # Unset is MISSING; a placeholder or short value is malformed → FAILED (§0.4 build rule).
        return [v for v in spec.required if not (env.get(v) or "").strip()]
    return [v for v in spec.required if is_placeholder(env.get(v))]


def check_app_secrets(env: dict[str, str]) -> ProbeResult:
    """Local checks only: tokens 32+ chars, hash is bcrypt (§0.4)."""
    problems = []
    for key in ("INTERNAL_TOKEN", "MCP_TOKEN"):
        v = env.get(key) or ""
        if is_placeholder(v):
            problems.append(f"{key} is a placeholder")
        elif len(v) < MIN_TOKEN_LEN:
            problems.append(f"{key} has {len(v)} characters (need {MIN_TOKEN_LEN}+)")
    h = env.get("DASH_PASS_HASH") or ""
    if is_placeholder(h):
        problems.append("DASH_PASS_HASH is a placeholder")
    elif not BCRYPT_RE.match(h):
        problems.append("DASH_PASS_HASH is not a bcrypt hash (keep it single-quoted)")
    if problems:
        return ProbeResult(False, error="; ".join(problems))
    user = env.get("DASH_USER") or "demo"
    return ProbeResult(True, f"tokens {mask(env['INTERNAL_TOKEN'])}, {mask(env['MCP_TOKEN'])}; "
                             f"dashboard user {user}, bcrypt hash present")


def rows_to_probe(env: dict[str, str], phase: str) -> list[str]:
    """Rows whose live probe should run: inputs present, and not FAKE in build."""
    keys = []
    for spec in ROWS:
        if spec.key == "app_secrets" or _missing(spec, env):
            continue
        if _is_fake(spec, env) and phase == "build":
            continue
        keys.append(spec.key)
    return keys


def evaluate(env: dict[str, str], phase: str,
             probe_results: dict[str, ProbeResult] | None = None) -> Report:
    """Pure: status precedence FAKE → MISSING → FAILED → READY, then the phase gate."""
    if phase not in PHASES:
        raise ValueError(f"unknown phase {phase!r}")
    probe_results = dict(probe_results or {})
    probe_results["app_secrets"] = check_app_secrets(env)
    secrets = _secret_values(env)
    rows: list[RowReport] = []
    probe_ok: dict[str, bool] = {}

    for spec in ROWS:
        fake = _is_fake(spec, env)
        missing = _missing(spec, env)
        result = probe_results.get(spec.key)
        probe = "skipped"
        if missing or (fake and phase == "build" and spec.key != "app_secrets"):
            result = None
        if result is not None:
            probe = "ready" if result.ok else "failed"
        probe_ok[spec.key] = probe == "ready"

        if fake:
            status = "FAKE"
            evidence = f"{spec.mode_var}={env.get(spec.mode_var, '')}"
            if spec.key == "object_storage":
                evidence += " → data/evidence/"
            if spec.key == "twilio":
                evidence += "; no call placed"
            if missing and spec.key != "aws":
                evidence += f"; {', '.join(missing)} not set"
            elif result is not None:
                evidence += "; probe ok, " + result.evidence if result.ok else "; probe FAILED: " + (result.error or "")
            next_step = spec.next_fake
        elif missing:
            status = "MISSING"
            evidence = _missing_evidence(missing, env)
            next_step = spec.next_missing
        elif result is None:
            status = "FAILED"
            evidence = "probe did not run"
            next_step = spec.next_failed
        elif not result.ok:
            status = "FAILED"
            evidence = result.error or "probe failed"
            next_step = spec.next_failed
        else:
            status = "READY"
            evidence = result.evidence
            next_step = "Nothing to do"
        rows.append(RowReport(spec.key, spec.name, status, probe,
                              scrub(evidence, secrets), next_step, list(spec.env)))

    failures = _gate_failures(env, phase, rows, probe_ok, probe_results)
    return Report(phase, not failures, [scrub(f, secrets) for f in failures],
                  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), rows)


def _missing_evidence(missing: list[str], env: dict[str, str]) -> str:
    parts = []
    for v in missing:
        raw = env.get(v)
        parts.append(f"{v} is the example value" if raw and raw.strip() else f"{v} not set")
    return "; ".join(parts) if len(parts) < 3 else ", ".join(missing) + " not set"


def _gate_failures(env, phase, rows, probe_ok, probe_results) -> list[str]:
    by_key = {r.key: r for r in rows}
    failures: list[str] = []
    app = by_key["app_secrets"]
    if app.status == "FAILED":
        failures.append(f"App secrets are malformed ({app.evidence}); run make secrets")
    if phase == "build":
        return failures

    for key in ("akamai_inference", "public_url", "twilio"):
        row = by_key[key]
        if not probe_ok[key]:
            failures.append(f"{row.name} probe must be READY (is {row.status}"
                            + (f": {row.evidence}" if row.status == "FAILED" else "") + ")")
    if phase == "integrate":
        return failures

    ai = env.get("AI_MODE", "")
    if ai != "live":
        failures.append(f"AI_MODE must be live (is {ai or 'unset'})")
    voice = env.get("VOICE_MODE", "")
    if voice != "twilio":
        failures.append(f"VOICE_MODE must be twilio (is {voice or 'unset'})")
    dev = by_key["devrev"]
    dev_probe = probe_results.get("devrev")
    if is_placeholder(env.get("PUBLIC_BASE_URL")):
        failures.append("POST /mcp without auth must return 401 (public URL not set)")
    elif dev_probe is None or not dev_probe.ok or "mcp 401" not in dev_probe.evidence:
        failures.append("POST /mcp without auth must return 401 ("
                        + (dev_probe.error if dev_probe and dev_probe.error else dev.evidence) + ")")
    version = env.get("EB_DATASET_VERSION", "")
    if is_placeholder(version) or version.startswith("public-"):
        failures.append(f"EB_DATASET_VERSION must be the SE's pinned version (is {version or 'unset'})")
    tw = by_key["twilio"]
    if tw.status != "READY":
        failures.append(f"Twilio balance must be at least ${MIN_TWILIO_BALANCE:.0f} (Twilio row is {tw.status})")
    return failures


# --------------------------------------------------------------------------- probes

def probe_akamai_inference(env: dict[str, str], timeout: float) -> ProbeResult:
    import httpx
    base = env["AKAMAI_BASE_URL"].rstrip("/")
    headers = {"Authorization": f"Bearer {env['AKAMAI_API_KEY']}"}
    model = env["MODEL_ID"]
    with httpx.Client(timeout=timeout, headers=headers) as c:
        r = c.get(f"{base}/models")
        if r.status_code != 200:
            return ProbeResult(False, error=f"GET /models returned {r.status_code}")
        ids = [m.get("id") for m in r.json().get("data", [])]
        if model not in ids:
            return ProbeResult(False, error=f"model {model} not listed (got {', '.join(map(str, ids[:5])) or 'none'})")
        t0 = time.perf_counter()
        r = c.post(f"{base}/chat/completions", json={
            "model": model, "max_tokens": 5,
            "messages": [{"role": "user", "content": "Say OK."}],
        })
        ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code != 200:
            return ProbeResult(False, error=f"completion returned {r.status_code}")
    return ProbeResult(True, f"{model} listed; 5-token completion {ms} ms; key {mask(env['AKAMAI_API_KEY'])}")


def probe_linode(env: dict[str, str], timeout: float) -> ProbeResult:
    import httpx
    r = httpx.get("https://api.linode.com/v4/profile", timeout=timeout,
                  headers={"Authorization": f"Bearer {env['LINODE_TOKEN']}"})
    if r.status_code != 200:
        return ProbeResult(False, error=f"GET /v4/profile returned {r.status_code}")
    return ProbeResult(True, f"user {r.json().get('username', '?')}; token {mask(env['LINODE_TOKEN'])}")


def probe_public_url(env: dict[str, str], timeout: float) -> ProbeResult:
    import httpx
    url = env["PUBLIC_BASE_URL"].rstrip("/") + "/healthz"
    r = httpx.get(url, timeout=timeout, verify=True, follow_redirects=False)
    if r.status_code != 200:
        return ProbeResult(False, error=f"GET /healthz returned {r.status_code}")
    return ProbeResult(True, f"{env['HOST']} /healthz 200, certificate valid")


def probe_object_storage(env: dict[str, str], timeout: float) -> ProbeResult:
    import boto3
    from botocore.config import Config
    cfg = Config(connect_timeout=timeout / 2, read_timeout=timeout / 2, retries={"max_attempts": 0})
    s3 = boto3.client("s3", endpoint_url=env["OBJ_ENDPOINT"], region_name=env["OBJ_REGION"],
                      aws_access_key_id=env["OBJ_ACCESS_KEY"], aws_secret_access_key=env["OBJ_SECRET_KEY"],
                      config=cfg)
    key = f"healthcheck/{uuid.uuid4()}.txt"
    bucket = env["OBJ_BUCKET"]
    s3.put_object(Bucket=bucket, Key=key, Body=b"callmeback healthcheck")
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    s3.delete_object(Bucket=bucket, Key=key)
    if body != b"callmeback healthcheck":
        return ProbeResult(False, error="read back a different object")
    return ProbeResult(True, f"put/get/delete ok on {bucket} ({env['OBJ_REGION']})")


def _twilio_client(env: dict[str, str], timeout: float):
    from twilio.http.http_client import TwilioHttpClient
    from twilio.rest import Client
    return Client(env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"],
                  http_client=TwilioHttpClient(timeout=timeout))


def probe_twilio(env: dict[str, str], timeout: float) -> ProbeResult:
    client = _twilio_client(env, timeout)
    sid = env["TWILIO_ACCOUNT_SID"]
    account = client.api.accounts(sid).fetch()
    if str(account.status).lower() != "active":
        return ProbeResult(False, error=f"account status is {account.status}")
    if str(account.type).lower() == "trial":
        return ProbeResult(False, error="trial account; upgrade it (§0.2 T+10)")
    bal = client.api.accounts(sid).balance.fetch()
    balance = float(bal.balance)
    currency = bal.currency or "USD"
    if balance < MIN_TWILIO_BALANCE:
        return ProbeResult(False, error=f"balance ${balance:.2f} < ${MIN_TWILIO_BALANCE:.0f}")
    numbers = client.incoming_phone_numbers.list(phone_number=env["TWILIO_FROM_NUMBER"], limit=1)
    if not numbers:
        return ProbeResult(False, error=f"number {mask(env['TWILIO_FROM_NUMBER'])} not on this account")
    caps = numbers[0].capabilities or {}
    if not caps.get("voice"):
        return ProbeResult(False, error="number has no voice capability")
    return ProbeResult(True, f"{account.type} account, balance {balance:.2f} {currency}, "
                             f"number {mask(env['TWILIO_FROM_NUMBER'])} has voice; no call placed")


def place_test_call(env: dict[str, str], timeout: float) -> str:
    """Dial DEMO_VENDOR_PHONE only (constitution IV). Returns the call SID."""
    client = _twilio_client(env, timeout)
    call = client.calls.create(
        to=env["DEMO_VENDOR_PHONE"], from_=env["TWILIO_FROM_NUMBER"],
        twiml="<Response><Say>Call Me Back readiness check.</Say></Response>",
    )
    return call.sid


def probe_devrev(env: dict[str, str], timeout: float) -> ProbeResult:
    data_dir = Path(env["EB_DATA_DIR"])
    if not data_dir.is_absolute():
        data_dir = REPO_ROOT / data_dir
    if not data_dir.is_dir():
        return ProbeResult(False, error=f"EB_DATA_DIR {env['EB_DATA_DIR']} not found")
    present = [f for f in EB_FOLDERS if (data_dir / f).is_dir()]
    if "crm_json_data" not in present:
        return ProbeResult(False, error=f"crm_json_data/ missing in {env['EB_DATA_DIR']} (found: {', '.join(present) or 'none'})")
    token = env.get("MCP_TOKEN") or ""
    if is_placeholder(token) or len(token) < MIN_TOKEN_LEN:
        return ProbeResult(False, error=f"MCP_TOKEN has {len(token)} characters (need {MIN_TOKEN_LEN}+)")
    evidence = f"{len(present)}/{len(EB_FOLDERS)} data folders; token {mask(token)}"
    if not is_placeholder(env.get("PUBLIC_BASE_URL")):
        import httpx
        r = httpx.post(env["PUBLIC_BASE_URL"].rstrip("/") + "/mcp", timeout=timeout, json={})
        if r.status_code != 401:
            return ProbeResult(False, error=f"unauthenticated POST /mcp returned {r.status_code}, expected 401")
        evidence += "; mcp 401 ok"
    return ProbeResult(True, evidence)


def probe_aws(env: dict[str, str], timeout: float) -> ProbeResult:
    import boto3
    from botocore.config import Config
    cfg = Config(connect_timeout=timeout / 2, read_timeout=timeout / 2, retries={"max_attempts": 0})
    kw = dict(region_name=env.get("AWS_REGION") or "us-west-2", aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
              aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"], config=cfg)
    ident = boto3.client("sts", **kw).get_caller_identity()
    model = env["BEDROCK_MODEL_ID"]
    boto3.client("bedrock-runtime", **kw).converse(
        modelId=model, messages=[{"role": "user", "content": [{"text": "Say OK."}]}],
        inferenceConfig={"maxTokens": 5})
    return ProbeResult(True, f"account {ident.get('Account', '?')}; {model} answered")


PROBES: dict[str, Callable[[dict[str, str], float], ProbeResult]] = {
    "akamai_inference": probe_akamai_inference,
    "akamai_cloud_api": probe_linode,
    "public_url": probe_public_url,
    "object_storage": probe_object_storage,
    "twilio": probe_twilio,
    "devrev": probe_devrev,
    "aws": probe_aws,
}


def _timed(fn, env, timeout) -> ProbeResult:
    t0 = time.perf_counter()
    try:
        result = fn(env, timeout)
    except Exception as exc:  # noqa: BLE001 — every failure becomes a FAILED row
        result = ProbeResult(False, error=f"{type(exc).__name__}: {exc}"[:200])
    result.duration_ms = int((time.perf_counter() - t0) * 1000)
    return result


def run_probes(env: dict[str, str], keys: Iterable[str], timeout: float = MAX_TIMEOUT) -> dict[str, ProbeResult]:
    """Run the named probes concurrently; each gets a hard deadline of `timeout` seconds."""
    keys = [k for k in keys if k in PROBES]
    results: dict[str, ProbeResult] = {}
    if not keys:
        return results
    pool = ThreadPoolExecutor(max_workers=len(keys), thread_name_prefix="probe")
    futures = {k: pool.submit(_timed, PROBES[k], env, timeout) for k in keys}
    deadline = time.monotonic() + timeout + 0.5
    for k, fut in futures.items():
        try:
            results[k] = fut.result(timeout=max(0.0, deadline - time.monotonic()))
        except FutureTimeout:
            results[k] = ProbeResult(False, error=f"timed out after {timeout:g} s", duration_ms=int(timeout * 1000))
    pool.shutdown(wait=False, cancel_futures=True)
    return results


# --------------------------------------------------------------------------- rendering

def render_json(report: Report) -> str:
    return json.dumps(asdict(report), indent=2)


def render_table(report: Report) -> str:
    rows = report.rows
    w_name = max(len(r.name) for r in rows) + 2
    w_ev = min(max(len(r.evidence) for r in rows), 60) + 2
    out = [f"Call Me Back readiness — phase: {report.phase} — {report.generated_at}",
           f"{'Integration':<{w_name}}{'Status':<9}{'Evidence':<{w_ev}}Next step"]
    for r in rows:
        ev = r.evidence if len(r.evidence) <= 60 else r.evidence[:57] + "..."
        out.append(f"{r.name:<{w_name}}{r.status:<9}{ev:<{w_ev}}{r.next_step}")
    out.append("")
    if report.ok:
        out.append(f"{report.phase} gate: PASS (exit 0)")
    else:
        out.append(f"{report.phase} gate: FAIL (exit 1)")
        out.extend(f"  - {f}" for f in report.failures)
    return "\n".join(out)


# --------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Call Me Back readiness matrix (PLAN.md §0.4)")
    parser.add_argument("--phase", default="build", choices=PHASES)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--call-test", action="store_true", help="place one call to DEMO_VENDOR_PHONE")
    parser.add_argument("--timeout", type=float, default=MAX_TIMEOUT)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    timeout = min(max(args.timeout, 0.5), MAX_TIMEOUT)

    env_path = Path(args.env_file)
    if env_path.exists() and not env_path.is_file():
        print(f"--env-file {env_path} is not a file", file=sys.stderr)
        return 2
    env = load_env(env_path)
    secrets = _secret_values(env)

    keys = rows_to_probe(env, args.phase)
    probe_results = run_probes(env, keys, timeout) if keys else {}
    report = evaluate(env, args.phase, probe_results)

    output = render_json(report) if args.as_json else render_table(report)
    print(scrub(output, secrets))

    if args.call_test:
        tw = probe_results.get("twilio")
        if tw is None or not tw.ok or is_placeholder(env.get("DEMO_VENDOR_PHONE")):
            print("call test skipped: Twilio row is not READY or DEMO_VENDOR_PHONE is unset", file=sys.stderr)
        else:
            try:
                sid = place_test_call(env, timeout)
                print(scrub(f"call test placed to {mask(env['DEMO_VENDOR_PHONE'])}: {sid}", secrets))
            except Exception as exc:  # noqa: BLE001
                print(scrub(f"call test failed: {type(exc).__name__}: {exc}", secrets), file=sys.stderr)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
