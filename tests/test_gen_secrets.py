"""scripts/gen_secrets.py: creates .env, fills only gaps, idempotent, quoting (spec 001 US3)."""
from __future__ import annotations

import re
import shutil
import socket
import stat
from pathlib import Path

import bcrypt
import pytest

from scripts import check_env as ce
from scripts import gen_secrets as gs

REPO = Path(__file__).resolve().parent.parent
TOKEN = "u1Jf8k2lQw9ZxV3bN7mC5pR0tY6sA4dE8gH2jK1lM3n"
HASH_LINE_RE = re.compile(r"^DASH_PASS_HASH='\$2a\$04\$[./A-Za-z0-9]{53}'$", re.M)


@pytest.fixture(autouse=True)
def no_network_clean_env(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    for name in ce.ALL_VARS:
        monkeypatch.delenv(name, raising=False)


def run(path: Path, capsys) -> str:
    assert gs.main(["--env-file", str(path), "--rounds", "4"]) == 0
    return capsys.readouterr().out


def password_from(out: str) -> str:
    m = re.search(r"password (\S+)", out)
    assert m, out
    return m.group(1)


def values(path: Path) -> dict[str, str]:
    from dotenv import dotenv_values
    return {k: (v or "") for k, v in dotenv_values(path).items()}


def test_creates_file_with_valid_secrets_and_prints_password_once(tmp_path, capsys):
    path = tmp_path / ".env"
    out = run(path, capsys)
    text = path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    v = values(path)
    for key in ("INTERNAL_TOKEN", "MCP_TOKEN"):
        assert len(v[key]) >= 32 and re.fullmatch(r"[A-Za-z0-9_-]+", v[key])
    assert v["DASH_USER"] == "demo"
    assert HASH_LINE_RE.search(text), text
    password = password_from(out)
    assert bcrypt.checkpw(password.encode(), v["DASH_PASS_HASH"].encode())
    assert out.count(password) == 1 and password not in text
    assert "Save it now" in out
    assert gs.GENERATED_HEADER in text


def test_replaces_placeholders_in_place_keeping_comments(tmp_path, capsys):
    path = tmp_path / ".env"
    shutil.copy(REPO / ".env.example", path)
    before = path.read_text().splitlines()
    run(path, capsys)
    after = path.read_text().splitlines()
    assert len(before) == len(after)  # no lines added: replaced in place
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    assert {before[i].split("=")[0] for i in changed} == {"INTERNAL_TOKEN", "MCP_TOKEN", "DASH_PASS_HASH"}
    mcp_line = next(l for l in after if l.startswith("MCP_TOKEN="))
    assert mcp_line.endswith("# entered in DevRev as the Personal Access Token")
    assert "DASH_USER=demo" in after
    assert re.search(r"^DASH_PASS_HASH='\$2a\$04\$[./A-Za-z0-9]{53}'$", "\n".join(after), re.M)


def test_keeps_valid_values_and_appends_missing(tmp_path, capsys):
    path = tmp_path / ".env"
    path.write_text(f"SOMETHING=else\nINTERNAL_TOKEN={TOKEN}\n")
    out = run(path, capsys)
    text = path.read_text()
    assert f"INTERNAL_TOKEN={TOKEN}\n" in text and text.startswith("SOMETHING=else\n")
    assert "INTERNAL_TOKEN: kept" in out and "MCP_TOKEN: written" in out
    tail = text.split(gs.GENERATED_HEADER)[1]
    assert "MCP_TOKEN=" in tail and "DASH_USER=demo" in tail and "DASH_PASS_HASH='" in tail


def test_second_run_is_byte_identical(tmp_path, capsys):
    path = tmp_path / ".env"
    run(path, capsys)
    first = path.read_bytes()
    out = run(path, capsys)
    assert "Nothing to do" in out and path.read_bytes() == first


def test_check_env_reports_app_secrets_ready(tmp_path, capsys):
    path = tmp_path / ".env"
    shutil.copy(REPO / ".env.example", path)
    assert next(r for r in ce.evaluate(values(path), "build").rows if r.key == "app_secrets").status == "FAILED"
    run(path, capsys)
    report = ce.evaluate(values(path), "build")
    row = next(r for r in report.rows if r.key == "app_secrets")
    assert row.status == "READY" and report.ok


def test_plan_changes_classification():
    plan = gs.plan_changes([f"INTERNAL_TOKEN={TOKEN}\n", "MCP_TOKEN=replace-with-x\n", "DASH_PASS_HASH='$2a$14$replace'\n"])
    assert plan["INTERNAL_TOKEN"][0] == "kept"
    assert plan["MCP_TOKEN"][0] == "replaced placeholder"
    assert plan["DASH_PASS_HASH"][0] == "replaced placeholder"
    assert plan["DASH_USER"] == ("written", None)
