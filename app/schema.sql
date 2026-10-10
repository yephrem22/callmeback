-- PLAN.md §7.2, verbatim. app/db.py executes this exact DDL.
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
