"""scripts/check_env.py: masking, placeholders, status precedence, phase gates,
and the I/O shell, all offline (PLAN.md §17.1 test_check_env.py row; spec 001 FR-018)."""
from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from scripts import check_env as ce
from scripts.check_env import ProbeResult, evaluate, is_placeholder, mask, scrub

REPO = Path(__file__).resolve().parent.parent
TOKEN = "u1Jf8k2lQw9ZxV3bN7mC5pR0tY6sA4dE8gH2jK1lM3n"  # 43 chars, urlsafe
GOOD_HASH = "$2a$14$abcdefghijklmnopqrstuvABCDEFGHIJKLMNOPQRSTUVWXYZ01234"  # 22 salt + 31 hash chars


@pytest.fixture(autouse=True)
def no_network_clean_env(monkeypatch):
    """Constitution VIII: nothing in pytest may call the network. Also drop every §7.1
    variable from os.environ (A's conftest exports the mode vars) so the file under
    test is authoritative, as it is for a user running `make check-env`."""
    def _deny(*args, **kwargs):
        raise AssertionError("network call in tests")
    monkeypatch.setattr(socket.socket, "connect", _deny)
    for name in ce.ALL_VARS:
        monkeypatch.delenv(name, raising=False)


def example_env() -> dict[str, str]:
    from dotenv import dotenv_values
    return {k: (v or "") for k, v in dotenv_values(REPO / ".env.example").items()}


def with_secrets(env: dict[str, str]) -> dict[str, str]:
    return {**env, "INTERNAL_TOKEN": TOKEN, "MCP_TOKEN": TOKEN[::-1], "DASH_PASS_HASH": GOOD_HASH}


def ok(evidence="probe ok, 120 ms") -> ProbeResult:
    return ProbeResult(True, evidence)


def failed(error) -> ProbeResult:
    return ProbeResult(False, error=error)


def row(report, key):
    return next(r for r in report.rows if r.key == key)


# --------------------------------------------------------------------- part A: pure helpers

def test_mask_never_reveals_more_than_last_four():
    assert mask("abc") == "••••"
    assert mask("abcd") == "••••"
    assert mask("") == "••••"
    assert mask(None) == "••••"
    m = mask("secret-value-7f3a")
    assert m.endswith("7f3a") and len(m) == 8 and "secret" not in m


@pytest.mark.parametrize("value", [
    "", None, "replace-me", "replace-with-a-generated-token-of-32-or-more-characters",
    "$2a$14$replace-with-caddy-hash-password-output", "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "172-105-12-34.sslip.io", "https://172-105-12-34.sslip.io", "team@example.com",
])
def test_placeholders(value):
    assert is_placeholder(value)


@pytest.mark.parametrize("value", ["hackathon-chat", "https://ws.akamai-workshops.com/v1", "us-ord-1", TOKEN])
def test_not_placeholders(value):
    assert not is_placeholder(value)


def test_scrub_masks_known_secrets_only():
    out = scrub("key sk-abcdefghij failed", ["sk-abcdefghij"])
    assert "••••ghij" in out and "sk-abcdefghij" not in out
    assert scrub("short s3cr3t here", ["s3cr3t"]) == "short s3cr3t here"


# --------------------------------------------------------------------- part B: evaluate

ORDER = ["akamai_inference", "akamai_cloud_api", "public_url", "object_storage",
         "twilio", "devrev", "aws", "app_secrets"]


def test_empty_env_build_passes_with_missing_or_fake():
    report = evaluate({}, "build")
    assert [r.key for r in report.rows] == ORDER
    assert report.ok and report.failures == []
    assert {r.status for r in report.rows} <= {"MISSING", "FAKE"}


def test_example_env_build_fails_on_placeholder_secrets():
    report = evaluate(example_env(), "build")
    assert not report.ok
    assert row(report, "app_secrets").status == "FAILED"
    assert any("make secrets" in f for f in report.failures)
    for key in ("akamai_inference", "object_storage", "twilio", "aws"):
        assert row(report, key).status == "FAKE"


def test_fake_mode_wins_over_credentials_and_probe_is_shown_in_integrate():
    env = with_secrets({**example_env(), "AKAMAI_API_KEY": "sk-live-0123456789abcdef", "AI_MODE": "off"})
    probes = {"akamai_inference": ok()}
    build = row(evaluate(env, "build", probes), "akamai_inference")
    assert build.status == "FAKE" and build.probe == "skipped"
    integ = row(evaluate(env, "integrate", probes), "akamai_inference")
    assert integ.status == "FAKE" and integ.probe == "ready" and "probe ok" in integ.evidence


def live_env() -> dict[str, str]:
    return with_secrets({
        **example_env(),
        "AKAMAI_API_KEY": "sk-live-0123456789abcdef",
        "HOST": "45-79-1-2.sslip.io", "PUBLIC_BASE_URL": "https://45-79-1-2.sslip.io",
        "TWILIO_ACCOUNT_SID": "AC" + "1" * 32, "TWILIO_AUTH_TOKEN": "tok-0123456789abcdef0123456789abcd",
        "TWILIO_FROM_NUMBER": "+18165550100",
    })


LIVE_PROBES = {"akamai_inference": ok(), "public_url": ok("200, cert ok"),
               "twilio": ok("Full account, balance 20.00 USD")}


def test_spec_ac3_integrate_passes_demo_fails_naming_requirements():
    env = live_env()  # AI_MODE=off, VOICE_MODE=simulated, no Object Storage key
    integ = evaluate(env, "integrate", LIVE_PROBES)
    assert integ.ok, integ.failures
    assert row(integ, "object_storage").status == "FAKE"
    demo = evaluate(env, "demo", LIVE_PROBES)
    assert not demo.ok
    text = "\n".join(demo.failures)
    for needle in ("AI_MODE", "VOICE_MODE", "/mcp", "EB_DATASET_VERSION", "balance"):
        assert needle in text, needle


def test_integrate_fails_when_a_gated_probe_is_missing():
    env = live_env()
    report = evaluate(env, "integrate", {k: v for k, v in LIVE_PROBES.items() if k != "twilio"})
    assert not report.ok and any("Twilio" in f for f in report.failures)


@pytest.mark.parametrize("reason", ["trial account; upgrade it", "balance $4.20 < $10", "number has no voice capability"])
def test_twilio_disqualifiers_are_failed_with_reason(reason):
    env = {**live_env(), "VOICE_MODE": "twilio"}
    r = row(evaluate(env, "integrate", {**LIVE_PROBES, "twilio": failed(reason)}), "twilio")
    assert r.status == "FAILED" and reason in r.evidence


def test_timeout_fails_only_that_row():
    env = {**live_env(), "LINODE_TOKEN": "lin-0123456789abcdef0123456789"}
    probes = {**LIVE_PROBES, "akamai_cloud_api": failed("timed out after 8 s")}
    report = evaluate(env, "integrate", probes)
    assert row(report, "akamai_cloud_api").status == "FAILED"
    assert "timed out" in row(report, "akamai_cloud_api").evidence
    assert report.ok  # Linode is never a gate requirement


@pytest.mark.parametrize("phase", ["build", "integrate", "demo"])
def test_aws_optional_never_fails(phase):
    report = evaluate({**live_env(), "LLM_FALLBACK": "none"}, phase, LIVE_PROBES)
    assert row(report, "aws").status == "FAKE"
    assert not any("AWS" in f for f in report.failures)


def test_public_release_version_is_fake_and_demo_names_it():
    env = {**live_env(), "EB_DATASET_VERSION": "public-2026-10-10"}
    assert row(evaluate(env, "build"), "devrev").status == "FAKE"
    demo = evaluate(env, "demo", LIVE_PROBES)
    assert any("EB_DATASET_VERSION" in f and "pinned" in f for f in demo.failures)


@pytest.mark.parametrize("phase", ["build", "integrate", "demo"])
def test_linode_token_absent_is_missing_and_never_gated(phase):
    report = evaluate(live_env(), phase, LIVE_PROBES)
    assert row(report, "akamai_cloud_api").status == "MISSING"
    assert not any("Cloud API" in f for f in report.failures)


def test_app_secrets_rules():
    base = example_env()
    short = {**base, "INTERNAL_TOKEN": "tooshort", "MCP_TOKEN": TOKEN, "DASH_PASS_HASH": GOOD_HASH}
    assert row(evaluate(short, "build"), "app_secrets").status == "FAILED"
    bad_hash = {**base, "INTERNAL_TOKEN": TOKEN, "MCP_TOKEN": TOKEN, "DASH_PASS_HASH": "plain-password"}
    assert row(evaluate(bad_hash, "build"), "app_secrets").status == "FAILED"
    good = with_secrets(base)
    r = row(evaluate(good, "build"), "app_secrets")
    assert r.status == "READY" and TOKEN not in r.evidence and TOKEN[-4:] in r.evidence


# --------------------------------------------------------------------- part C: I/O shell

def test_main_without_env_file_passes_build(tmp_path, capsys, monkeypatch):
    calls = []
    monkeypatch.setattr(ce, "run_probes", lambda *a, **k: calls.append(a) or {})
    rc = ce.main(["--env-file", str(tmp_path / "none.env")])
    out = capsys.readouterr().out
    assert rc == 0 and "build gate: PASS" in out
    assert calls == []  # nothing to probe with an empty env


def test_main_json_shape(tmp_path, capsys):
    rc = ce.main(["--env-file", str(tmp_path / "none.env"), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert rc == 0 and data["phase"] == "build" and data["ok"] is True and data["failures"] == []
    assert len(data["rows"]) == 8 and data["generated_at"].endswith("Z")
    for r in data["rows"]:
        assert set(r) == {"key", "name", "status", "probe", "evidence", "next_step", "env"}
        assert all(name.isupper() for name in r["env"])


@pytest.mark.parametrize("as_json", [False, True])
def test_output_never_contains_secret_prefix(tmp_path, capsys, monkeypatch, as_json):
    secret = "sk-live-0123456789abcdef"
    env_file = tmp_path / ".env"
    env_file.write_text(f"AKAMAI_BASE_URL=https://ws.akamai-workshops.com/v1\nMODEL_ID=hackathon-chat\n"
                        f"AKAMAI_API_KEY={secret}\nAI_MODE=off\nINTERNAL_TOKEN=x\n")
    # even a probe that echoes the secret back must not leak it
    monkeypatch.setattr(ce, "run_probes", lambda env, keys, t: {"akamai_inference": failed(f"bad key {secret}")})
    args = ["--env-file", str(env_file), "--phase", "integrate"] + (["--json"] if as_json else [])
    ce.main(args)
    out = capsys.readouterr().out
    assert secret[:-4] not in out and secret[-4:] in out


def test_unknown_phase_is_usage_error(capsys):
    assert ce.main(["--phase", "nope"]) == 2


def test_no_call_without_call_test(tmp_path, capsys, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("\n".join([
        "VOICE_MODE=twilio", "TWILIO_ACCOUNT_SID=AC" + "1" * 32,
        "TWILIO_AUTH_TOKEN=tok-0123456789abcdef0123456789abcd", "TWILIO_FROM_NUMBER=+18165550100",
        "DEMO_VENDOR_PHONE=+18165550199", f"INTERNAL_TOKEN={TOKEN}", f"MCP_TOKEN={TOKEN}", f"DASH_PASS_HASH='{GOOD_HASH}'",
    ]))
    monkeypatch.setattr(ce, "run_probes", lambda env, keys, t: {"twilio": ok("Full account")})
    dialled = []
    monkeypatch.setattr(ce, "place_test_call", lambda env, t: dialled.append(env["DEMO_VENDOR_PHONE"]) or "CA123")
    ce.main(["--env-file", str(env_file)])
    assert dialled == []
    ce.main(["--env-file", str(env_file), "--call-test"])
    assert dialled == ["+18165550199"]
    assert "CA123" in capsys.readouterr().out


def test_rows_to_probe_skips_missing_and_fake_in_build():
    assert ce.rows_to_probe({}, "build") == []
    env = live_env()
    # public_url has inputs and no mode; devrev's probe is local folder checks (EB_DATA_DIR + MCP_TOKEN set)
    assert ce.rows_to_probe(env, "build") == ["public_url", "devrev"]
    assert set(ce.rows_to_probe(env, "integrate")) == {"akamai_inference", "public_url", "twilio", "devrev"}


def test_pure_core_imports_no_network_clients():
    """Network clients are imported lazily inside the probe functions, never at module scope."""
    import subprocess
    import sys
    code = ("import sys; import scripts.check_env, scripts.gen_secrets; "
            "print(sorted(m for m in ('twilio', 'boto3', 'httpx', 'botocore') if m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]", out


# --------------------------------------------------------------------- part D: zero credentials (US2)

def test_example_env_with_secrets_is_a_complete_fake_mode_config():
    env = with_secrets(example_env())
    all_ok = {key: ok() for key in ce.PROBES}
    report = evaluate(env, "build", all_ok)
    assert report.ok and report.failures == []
    for key in ("akamai_inference", "object_storage", "twilio", "aws"):
        assert row(report, key).status == "FAKE", key  # mode wins over credentials (FR-010)
    assert row(report, "app_secrets").status == "READY"
    # and with nothing probed at all (no network), the result is the same
    assert evaluate(env, "build").ok


def test_mode_variable_makes_row_fake_even_with_real_credentials():
    env = with_secrets({**example_env(), "OBJ_ACCESS_KEY": "AKIA0123456789ABCDEF",
                        "OBJ_SECRET_KEY": "s3cr3t-0123456789abcdef0123456789", "STORAGE_MODE": "local"})
    r = row(evaluate(env, "integrate", {"object_storage": ok("put/get/delete ok")}), "object_storage")
    assert r.status == "FAKE" and r.probe == "ready" and "probe ok" in r.evidence
    assert "s3cr3t-0123456789abcdef" not in r.evidence
