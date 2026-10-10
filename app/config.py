"""Settings loaded from the environment (names and defaults per PLAN.md §7.1).

Never log or print values from here. `make check-env` (spec 001) is the only
thing that reports on secrets, and it masks them.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: str) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return int(default)


def _path(name: str, default: str) -> Path:
    raw = os.environ.get(name, default)
    p = Path(raw)
    return p if p.is_absolute() else REPO_ROOT / p


@dataclass
class Settings:
    # public URL
    public_base_url: str = field(default_factory=lambda: os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"))
    host: str = field(default_factory=lambda: os.environ.get("HOST", "localhost"))
    acme_email: str = field(default_factory=lambda: os.environ.get("ACME_EMAIL", ""))

    # Akamai hosted inference
    akamai_base_url: str = field(default_factory=lambda: os.environ.get("AKAMAI_BASE_URL", "https://ws.akamai-workshops.com/v1"))
    akamai_api_key: str = field(default_factory=lambda: os.environ.get("AKAMAI_API_KEY", ""))
    model_id: str = field(default_factory=lambda: os.environ.get("MODEL_ID", "hackathon-chat"))
    llm_streaming: bool = field(default_factory=lambda: _bool("LLM_STREAMING", "0"))
    llm_rpm: int = field(default_factory=lambda: _int("LLM_RPM", "45"))
    ai_mode: str = field(default_factory=lambda: os.environ.get("AI_MODE", "off"))
    timeout_intake_s: int = field(default_factory=lambda: _int("TIMEOUT_INTAKE_S", "20"))
    timeout_analyst_s: int = field(default_factory=lambda: _int("TIMEOUT_ANALYST_S", "45"))
    timeout_verifier_s: int = field(default_factory=lambda: _int("TIMEOUT_VERIFIER_S", "15"))
    timeout_payments_s: int = field(default_factory=lambda: _int("TIMEOUT_PAYMENTS_S", "30"))
    llm_fallback: str = field(default_factory=lambda: os.environ.get("LLM_FALLBACK", "none"))

    # Twilio
    voice_mode: str = field(default_factory=lambda: os.environ.get("VOICE_MODE", "simulated"))
    twilio_account_sid: str = field(default_factory=lambda: os.environ.get("TWILIO_ACCOUNT_SID", ""))
    twilio_auth_token: str = field(default_factory=lambda: os.environ.get("TWILIO_AUTH_TOKEN", ""))
    twilio_from_number: str = field(default_factory=lambda: os.environ.get("TWILIO_FROM_NUMBER", ""))
    twilio_validate_signature: bool = field(default_factory=lambda: _bool("TWILIO_VALIDATE_SIGNATURE", "1"))

    # demo
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", "1"))
    demo_vendor_phone: str = field(default_factory=lambda: os.environ.get("DEMO_VENDOR_PHONE", "+18165550199"))
    payer_name: str = field(default_factory=lambda: os.environ.get("PAYER_NAME", "Northgate Manufacturing"))
    deploy_label: str = field(default_factory=lambda: os.environ.get("DEPLOY_LABEL", "Akamai Cloud, Chicago (us-ord)"))

    # dashboard / internal / mcp
    dash_user: str = field(default_factory=lambda: os.environ.get("DASH_USER", "demo"))
    internal_token: str = field(default_factory=lambda: os.environ.get("INTERNAL_TOKEN", ""))
    mcp_token: str = field(default_factory=lambda: os.environ.get("MCP_TOKEN", ""))
    mcp_port: int = field(default_factory=lambda: _int("MCP_PORT", "8001"))
    mcp_allowed_hosts: str = field(default_factory=lambda: os.environ.get("MCP_ALLOWED_HOSTS", ""))
    eb_data_dir: str = field(default_factory=lambda: os.environ.get("EB_DATA_DIR", "/eb_data"))
    eb_dataset_version: str = field(default_factory=lambda: os.environ.get("EB_DATASET_VERSION", ""))
    app_internal_url: str = field(default_factory=lambda: os.environ.get("APP_INTERNAL_URL", "http://app:8000"))
    devrev_org_url: str = field(default_factory=lambda: os.environ.get("DEVREV_ORG_URL", ""))

    # storage
    storage_mode: str = field(default_factory=lambda: os.environ.get("STORAGE_MODE", "local"))
    obj_endpoint: str = field(default_factory=lambda: os.environ.get("OBJ_ENDPOINT", ""))
    obj_region: str = field(default_factory=lambda: os.environ.get("OBJ_REGION", ""))
    obj_bucket: str = field(default_factory=lambda: os.environ.get("OBJ_BUCKET", ""))
    obj_access_key: str = field(default_factory=lambda: os.environ.get("OBJ_ACCESS_KEY", ""))
    obj_secret_key: str = field(default_factory=lambda: os.environ.get("OBJ_SECRET_KEY", ""))
    db_path: Path = field(default_factory=lambda: _path("DB_PATH", "data/app.db"))

    # AWS (optional)
    aws_region: str = field(default_factory=lambda: os.environ.get("AWS_REGION", "us-west-2"))
    bedrock_model_id: str = field(default_factory=lambda: os.environ.get("BEDROCK_MODEL_ID", ""))

    @property
    def ai_on(self) -> bool:
        return self.ai_mode == "live"


def _load() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)
    return Settings()


S: Settings = _load()


def reload() -> Settings:
    """Re-read the environment (tests change env vars between cases)."""
    global S
    S = _load()
    return S
