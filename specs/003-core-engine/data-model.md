# Data Model: Core Engine (spec 003)

**Source of truth**: PLAN.md §7.2 (schema), §7.3 (status machine), §7.4 (core models). The three sections below are copied verbatim from PLAN.md on 2026-10-10 and are **frozen** at the end of this feature's phase 1 (milestone A1). Do not edit them here; if a change is truly needed, change PLAN.md with both builders' agreement and re-copy.

Entity overview (business meaning) is in `spec.md` → Key Entities. Relationships:

- `vendors` 1 → many `invoice_history`, `vendor_bank_history`, `invoices` (via `vendor_id`).
- `invoices` 1 → many `verifications` (via `subject_id`, `kind='invoice'`), 1 → 0..1 `payments` (`UNIQUE(invoice_id)`), 1 → many `audit_log` rows (via `subject_id`), 1 → many `agent_traces`.
- `change_cases` 1 → many `verifications` (`kind='change_case'`); change cases never touch invoices, payments or vendors.
- `audit_log` is one global hash chain ordered by `seq`.

Validation rules that live in code, per PLAN.md:

- `state.transition()` enforces the §7.3 table and hold-reason legality atomically (`BEGIN IMMEDIATE`, compare-and-set on status, `version+1`, audit `status_changed` in the same transaction).
- `ledger.can_release()` enforces §13.1; `payments.invoice_id` is UNIQUE so a double release is impossible.
- Masking (§6) applies to every value leaving the DB except the Intake agent's raw email.
- `RiskResult.policy_version = "2026-10-10.1"`.

---

## PLAN.md §7.2 Database schema (verbatim)

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS vendors (
  id TEXT PRIMARY KEY,                 -- 'ven_acme'
  name TEXT NOT NULL,
  domains TEXT NOT NULL,               -- JSON array of lowercase domains
  phone_on_file TEXT NOT NULL,         -- E.164
  bank_name TEXT,
  routing TEXT NOT NULL,
  account TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vendor_bank_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  vendor_id TEXT NOT NULL REFERENCES vendors(id),
  old_bank_name TEXT, old_routing TEXT, old_account TEXT,
  new_bank_name TEXT, new_routing TEXT, new_account TEXT,
  invoice_id TEXT NOT NULL, verification_id TEXT NOT NULL,
  changed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoice_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  vendor_id TEXT NOT NULL REFERENCES vendors(id),
  invoice_number TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  paid_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,                -- 'sample' | 'upload'
  sample_name TEXT,
  raw_sha256 TEXT NOT NULL,
  raw_object_key TEXT,                 -- Object Storage key, nullable
  from_name TEXT, from_email TEXT, from_domain TEXT,
  reply_to TEXT, reply_to_domain TEXT,
  subject TEXT, received_at TEXT,
  body_text TEXT NOT NULL,
  extraction TEXT,                     -- JSON ExtractionResult
  vendor_id TEXT REFERENCES vendors(id),
  risk TEXT,                           -- JSON RiskResult
  analyst TEXT,                        -- JSON {"status": "pending|done|fallback|error", "report": AnalystReport|null}
  memo TEXT,                           -- JSON {"text": str, "by": "agent|fallback"}
  review TEXT,                         -- JSON {"decision": "approve|reject", "note": str, "at": ts}
  status TEXT NOT NULL,
  hold_reason TEXT,
  ai_fallback INTEGER NOT NULL DEFAULT 0,  -- 1 if any agent fell back to rules
  version INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verifications (
  id TEXT PRIMARY KEY,                 -- 'ver_...'
  subject_id TEXT NOT NULL,            -- invoice id or change case id
  kind TEXT NOT NULL,                  -- 'invoice' | 'change_case'
  token_hash TEXT NOT NULL UNIQUE,     -- sha256 hex of the URL token
  expires_at TEXT NOT NULL,            -- created + 15 min
  call_sid TEXT,
  phone_called TEXT NOT NULL,          -- E.164
  source TEXT NOT NULL,                -- 'twilio' | 'simulated'
  step TEXT NOT NULL,                  -- 'created'|'placed'|'ringing'|'answered'|'asked'|'awaiting_last4'|'verifying'|'done'
  attempts INTEGER NOT NULL DEFAULT 0,
  answer_channel TEXT,                 -- 'dtmf' | 'speech' | NULL
  digits TEXT, speech TEXT, speech_confidence REAL,
  det_label TEXT,                      -- 'YES'|'NO'|'UNCLEAR'
  llm_label TEXT, llm_rationale TEXT,  -- 'CONFIRMED'|'DENIED'|'UNCLEAR'|NULL
  last4_ok INTEGER,                    -- 1 | 0 | NULL
  final_label TEXT,                    -- 'CONFIRMED'|'DENIED'|'UNCLEAR'|'NO_ANSWER'|'LAST4_MISMATCH'|'VERIFIER_DISAGREED'|'SUPERSEDED'
  events TEXT NOT NULL DEFAULT '[]',   -- JSON timeline [{"ts","label","detail"}]
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
  id TEXT PRIMARY KEY,
  invoice_id TEXT NOT NULL UNIQUE REFERENCES invoices(id),   -- UNIQUE = no double release
  amount_cents INTEGER NOT NULL,
  bank_name TEXT, routing TEXT NOT NULL, account TEXT NOT NULL,
  method TEXT NOT NULL DEFAULT 'ACH-CCD',
  effective_date TEXT NOT NULL,        -- next business day
  released_at TEXT NOT NULL,
  released_by TEXT NOT NULL            -- 'agent:payments' | 'policy:auto'
);
CREATE TABLE IF NOT EXISTS audit_log (
  seq INTEGER PRIMARY KEY,             -- assigned explicitly: last seq + 1
  ts TEXT NOT NULL,
  subject_id TEXT,
  actor TEXT NOT NULL,                 -- see §13.3
  event TEXT NOT NULL,                 -- see §13.3
  data TEXT NOT NULL,                  -- canonical JSON, masked
  prev_hash TEXT NOT NULL,
  hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_traces (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  subject_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  agent TEXT NOT NULL,                 -- 'intake'|'analyst'|'verifier'|'payments'|'payments:redteam'
  kind TEXT NOT NULL,                  -- 'run_start'|'model_call'|'tool_call'|'guard_allow'|'guard_block'|'run_end'|'fallback'|'error'
  name TEXT,                           -- tool name, if any
  summary TEXT,                        -- ≤ 200 chars, masked
  duration_ms INTEGER,
  ts TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS change_cases (
  id TEXT PRIMARY KEY,                 -- 'cc_...'
  idempotency_key TEXT NOT NULL UNIQUE,
  account_ref TEXT NOT NULL,           -- JSON {"id","name","source_ref"}
  requested_change TEXT NOT NULL,      -- 'billing_contact'|'payment_details'|'remit_address'|'admin_contact'|'other'
  sender_email TEXT NOT NULL,
  request_excerpt TEXT NOT NULL,       -- ≤ 500 chars
  signals TEXT NOT NULL,               -- JSON
  callback_target TEXT,                -- JSON or NULL
  source_refs TEXT NOT NULL,           -- JSON
  dataset_version TEXT,
  status TEXT NOT NULL,                -- 'OPEN'|'CALLING'|'CONFIRMED'|'DENIED'|'UNCLEAR'|'NO_ANSWER'|'CLOSED'
  created_by TEXT NOT NULL,            -- 'devrev'
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

---

## PLAN.md §7.3 Status machine (verbatim)

```
Status: RECEIVED, EXTRACTED, SCORED, AUTO_APPROVED, NEEDS_REVIEW, REVIEW_APPROVED,
        CALL_PENDING, CALLING, VERIFYING, CONFIRMED, RELEASED, HELD, FAILED

HoldReason: DENIED_BY_VENDOR, UNCLEAR_ANSWER, NO_ANSWER, LAST4_MISMATCH, VERIFIER_DISAGREED,
            REVIEW_REJECTED, UNKNOWN_VENDOR, CALL_FAILED, AGENT_HOLD
```

| From | Allowed to |
|---|---|
| RECEIVED | EXTRACTED, FAILED |
| EXTRACTED | SCORED, FAILED |
| SCORED | AUTO_APPROVED, NEEDS_REVIEW, CALL_PENDING, HELD (only UNKNOWN_VENDOR) |
| AUTO_APPROVED | RELEASED, HELD (AGENT_HOLD) |
| NEEDS_REVIEW | REVIEW_APPROVED, HELD (REVIEW_REJECTED) |
| REVIEW_APPROVED | RELEASED, HELD (AGENT_HOLD) |
| CALL_PENDING | CALLING, HELD (CALL_FAILED) |
| CALLING | VERIFYING, CONFIRMED, HELD (DENIED_BY_VENDOR, UNCLEAR_ANSWER, NO_ANSWER, LAST4_MISMATCH) |
| VERIFYING | CONFIRMED, HELD (VERIFIER_DISAGREED, UNCLEAR_ANSWER) |
| CONFIRMED | RELEASED, HELD (AGENT_HOLD) |
| HELD | CALL_PENDING (retry, only when hold_reason ∈ {UNCLEAR_ANSWER, NO_ANSWER, CALL_FAILED, VERIFIER_DISAGREED}) |
| RELEASED, FAILED | terminal (DEMO reset wipes everything) |

```python
def transition(invoice_id: str, to: Status, *, hold_reason: HoldReason | None = None,
               actor: str, detail: dict | None = None) -> bool:
    """Atomic compare-and-set.
    UPDATE invoices SET status=?, hold_reason=?, version=version+1, updated_at=?
     WHERE id=? AND status IN (<legal from-states for `to`>)
    Returns True if the row changed and writes an audit 'status_changed' event.
    Returns False if the invoice is already in `to` (idempotent no-op; webhooks retry).
    Raises IllegalTransition otherwise.
    HELD requires hold_reason, and hold_reason must be allowed for the from-state.
    The UPDATE and its audit event commit in one `BEGIN IMMEDIATE` transaction."""
```

---

## PLAN.md §7.4 Core models (verbatim)

```python
Tier = Literal["GREEN", "YELLOW", "RED"]
Action = Literal["AUTO_RELEASE", "REVIEW", "CALLBACK", "HOLD_MANUAL"]

class Flag(BaseModel):
    code: str                 # e.g. "BANK_CHANGED" (full list in §10.2)
    points: int
    title: str                # user-facing, e.g. "Bank details differ from vendor record"
    detail: str               # specific: "acme-supp1y.com imitates acme-supply.com ('1' in place of 'l')"
    evidence: list[str] = []  # short quotes or values (masked)

class RiskResult(BaseModel):
    flags: list[Flag]
    points: int               # uncapped sum
    tier: Tier
    action: Action
    vendor_id: str | None
    sender_status: Literal["KNOWN", "LOOKALIKE", "UNRECOGNIZED", "NO_VENDOR"]
    bank_changed: bool
    proposed_bank_name: str | None
    proposed_routing: str | None   # raw in DB JSON; masked in API output
    proposed_account: str | None   # raw in DB JSON; masked in API output
    amount_cents: int | None
    median_cents: int | None
    policy_version: str = "2026-10-10.1"

class FieldValue(BaseModel):
    value: str | None
    source: Literal["regex", "llm", "both", "header", "none"]
    llm_value: str | None = None
    mismatch: bool = False    # regex and LLM disagreed; regex won

class ExtractionResult(BaseModel):
    vendor_name: FieldValue
    invoice_number: FieldValue
    amount: FieldValue        # normalized "48750.00"
    due_date: FieldValue
    bank_name: FieldValue
    routing_number: FieldValue
    account_number: FieldValue
    phone_numbers_in_email: list[str]
    requests_payment_change: bool | None   # LLM opinion, advisory only
    llm_status: Literal["pending", "ok", "fallback", "error"]   # "pending" while the fast path's Intake agent runs

class InvoiceExtraction(BaseModel):        # Intake agent structured output (see §11.4 for validators)
    vendor_name: str | None
    invoice_number: str | None
    amount: str | None                     # exactly as written, e.g. "$48,750.00"
    due_date: str | None
    bank_name: str | None
    routing_number: str | None             # digits exactly as in the email
    account_number: str | None
    phone_numbers: list[str] = []
    requests_payment_change: bool = False
    pressure_phrases: list[str] = []
    verification_avoidance_phrases: list[str] = []
    instructions_aimed_at_ai: bool = False

class AnalystReport(BaseModel):
    headline: str                          # ≤ 12 words
    explanation: str                       # ≤ 90 words, for a busy AP clerk
    cited_flags: list[str]                 # must be a subset of RiskResult flag codes
    additional_concerns: list[str] = []    # advisory; never changes points
    recommended_next_step: str

class VerifierLabel(BaseModel):
    label: Literal["CONFIRMED", "DENIED", "UNCLEAR"]
    rationale: str                         # ≤ 200 chars

class CallContext(BaseModel):
    verification_id: str
    subject_id: str
    kind: Literal["invoice", "change_case"]
    payer_name: str
    counterparty_name: str                 # vendor name or account name
    amount_cents: int | None
    change_type: Literal["bank_account", "billing_contact", "payment_details", "remit_address", "admin_contact", "other"]
    expected_last4: str | None             # only for bank_account
    phone_to_call: str                     # E.164; change cases always DEMO_VENDOR_PHONE
    attempts: int
```
