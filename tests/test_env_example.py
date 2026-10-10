""".env.example is PLAN.md §7.1 verbatim and selects every fake mode (spec 001 US2, FR-011)."""
from __future__ import annotations

import re
from pathlib import Path

from dotenv import dotenv_values

from scripts import check_env as ce

REPO = Path(__file__).resolve().parent.parent

EXPECTED_VARS = [
    "PUBLIC_BASE_URL", "HOST", "ACME_EMAIL",
    "AKAMAI_BASE_URL", "AKAMAI_API_KEY", "MODEL_ID", "LLM_STREAMING", "LLM_RPM", "AI_MODE",
    "TIMEOUT_INTAKE_S", "TIMEOUT_ANALYST_S", "TIMEOUT_VERIFIER_S", "TIMEOUT_PAYMENTS_S", "LLM_FALLBACK",
    "VOICE_MODE", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_NUMBER", "TWILIO_VALIDATE_SIGNATURE",
    "DEMO_MODE", "DEMO_VENDOR_PHONE", "PAYER_NAME", "DEPLOY_LABEL",
    "DASH_USER", "DASH_PASS_HASH",
    "INTERNAL_TOKEN",
    "MCP_TOKEN", "MCP_PORT", "MCP_ALLOWED_HOSTS", "EB_DATA_DIR", "EB_DATASET_VERSION", "APP_INTERNAL_URL", "DEVREV_ORG_URL",
    "STORAGE_MODE", "OBJ_ENDPOINT", "OBJ_REGION", "OBJ_BUCKET", "OBJ_ACCESS_KEY", "OBJ_SECRET_KEY",
    "DB_PATH",
    "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "BEDROCK_MODEL_ID",
    "LINODE_TOKEN",
]


def example() -> dict[str, str]:
    return {k: (v or "") for k, v in dotenv_values(REPO / ".env.example").items()}


def test_exactly_the_section_7_1_variables_in_order():
    assert list(example()) == EXPECTED_VARS
    assert len(EXPECTED_VARS) == 45


def test_defaults_select_every_fake_mode():
    env = example()
    assert env["AI_MODE"] == "off"
    assert env["VOICE_MODE"] == "simulated"
    assert env["STORAGE_MODE"] == "local"
    assert env["LLM_FALLBACK"] == "none"
    assert env["TWILIO_VALIDATE_SIGNATURE"] == "1"
    assert env["DEMO_MODE"] == "1"


def test_every_secret_is_empty_or_a_placeholder():
    env = example()
    for name in ce.SECRET_VARS:
        assert ce.is_placeholder(env[name]), name
    assert env["DASH_PASS_HASH"].startswith("$2a$14$replace")  # single quotes stripped by dotenv


def test_file_matches_plan_md_section_7_1_verbatim():
    plan = (REPO / "PLAN.md").read_text().splitlines()
    start = next(i for i, l in enumerate(plan) if l.startswith("### 7.1 Environment variables"))
    fence = next(i for i in range(start, len(plan)) if plan[i].strip() == "```bash")
    end = next(i for i in range(fence + 1, len(plan)) if plan[i].strip() == "```")
    assert plan[fence + 1:end] == (REPO / ".env.example").read_text().splitlines()


def test_no_real_looking_values_leak_into_example():
    text = (REPO / ".env.example").read_text()
    assert not re.search(r"AC[0-9a-f]{32}", text)          # a real Twilio SID
    assert not re.search(r"\$2a\$14\$[./A-Za-z0-9]{53}", text)  # a real bcrypt hash
