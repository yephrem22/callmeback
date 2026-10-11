"""SC-008: the live API returns every field the dashboard's fixtures have (web/src/fixtures).

The five PLAN.md §8.4 stories are played through the API (AI off); for each scenario's final
fixture step, and for the list/health/stats/payments/vendors/audit fixtures, every nested key
path in the fixture must exist in the live response. Extra live keys are allowed.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

FIXTURES = config.REPO_ROOT / "web" / "src" / "fixtures"
INDEX = json.loads((FIXTURES / "index.json").read_text())
SAMPLE = {"acme_normal": "01_acme_normal", "acme_fraud": "02_acme_fraud",
          "heartland_bank_change": "03_heartland_bank_change", "prairie_review": "04_prairie_review",
          "unknown_vendor": "05_unknown_vendor"}
VIEWS = {"/api/invoices": "invoices_list.json", "/api/health": "health.json", "/api/stats": "stats.json",
         "/api/payments": "payments.json", "/api/vendors": "vendors.json", "/api/audit": "audit.json"}


def _paths(x, prefix: str = "") -> set[str]:
    out: set[str] = set()
    if isinstance(x, dict):
        for k, v in x.items():
            out.add(f"{prefix}.{k}")
            out |= _paths(v, f"{prefix}.{k}")
    elif isinstance(x, list):
        for v in x:
            out |= _paths(v, f"{prefix}[]")
    return out


@pytest.fixture
def played(db):
    """The five stories driven to their final states; returns (client, {scenario: invoice_id})."""
    with TestClient(app) as client:
        ids = {}
        for scenario, sample in SAMPLE.items():
            ids[scenario] = client.post("/api/invoices/from-sample", json={"name": sample}).json()["id"]
        client.post("/api/demo/simulate-answer", json={"subject_id": ids["acme_fraud"], "answer": "no", "last4": None})
        client.post("/api/demo/simulate-answer",
                    json={"subject_id": ids["heartland_bank_change"], "answer": "yes", "last4": "4455"})
        client.post(f"/api/invoices/{ids['prairie_review']}/review", json={"decision": "approve", "note": "renewal"})
        yield client, ids


def test_every_scenario_is_covered():
    assert set(INDEX) == set(SAMPLE)


@pytest.mark.parametrize("scenario", sorted(SAMPLE))
def test_invoice_detail_has_every_fixture_field(played, scenario):
    client, ids = played
    final = INDEX[scenario][-1]
    fixture = json.loads((FIXTURES / final["file"]).read_text())
    live = client.get(f"/api/invoices/{ids[scenario]}").json()
    assert (live["status"], live["hold_reason"]) == (final["status"], final["hold_reason"])
    missing = sorted(_paths(fixture) - _paths(live))
    assert missing == [], f"{scenario}: fixture fields absent from the live API: {missing}"


@pytest.mark.parametrize("endpoint", sorted(VIEWS))
def test_views_have_every_fixture_field(played, endpoint):
    client, _ = played
    fixture = json.loads((FIXTURES / VIEWS[endpoint]).read_text())
    missing = sorted(_paths(fixture) - _paths(client.get(endpoint).json()))
    assert missing == [], f"{endpoint}: fixture fields absent from the live API: {missing}"
