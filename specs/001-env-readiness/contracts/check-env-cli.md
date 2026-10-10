# Contract: `scripts/check_env.py`

Invoked as `make check-env [PHASE=build|integrate|demo] [ARGS="…"]` or directly with the project interpreter. Behaviour is PLAN.md §0.4; this file only fixes the command-line surface and the output shapes.

## Arguments

| flag | default | meaning |
|---|---|---|
| `--phase {build,integrate,demo}` | `build` | which gate decides the exit code (§0.4) |
| `--json` | off | print the Report as JSON instead of the table |
| `--env-file PATH` | `.env` at the repo root | file to read (tests pass a temp file); `os.environ` overlays it |
| `--call-test` | off | after the Twilio probe, place one call to `DEMO_VENDOR_PHONE` and print its SID. Without this flag no call is ever placed |
| `--timeout SECONDS` | `8` | per-probe deadline; the maximum is 8 |

Environment: `PHASE` is not read by the script (the Makefile maps it to `--phase`).

## Exit codes

- `0`: the gate for `--phase` is met.
- `1`: the gate is not met (every unmet requirement is listed under `failures`).
- `2`: usage error (unknown phase, unreadable `--env-file`).

The script never raises to the shell for a probe failure; those become FAILED rows.

## Table output (human)

```
Call Me Back readiness — phase: build — 2026-10-10T16:02:11Z
Integration                  Status   Evidence                                 Next step
Akamai inference             FAKE     AI_MODE=off; key ••••7f3a; probe skipped  Set AI_MODE=live once the key works (§0.4)
Akamai Cloud API             MISSING  LINODE_TOKEN not set                      Create a Linode token, laptop only (§0.2 T+25)
Public HTTPS URL             MISSING  PUBLIC_BASE_URL is the example value      Provision the VM (spec 002, §16.1)
Object Storage               FAKE     STORAGE_MODE=local → data/evidence/       Create the bucket and key (§16.3)
Twilio                       FAKE     VOICE_MODE=simulated; no call placed      Upgrade Twilio and buy a Voice number (§0.2 T+10)
DevRev and Enterprise-Bench  MISSING  EB_DATA_DIR /eb_data not found            Download the public release; ask the SE for the export (§15.2)
AWS (optional)               FAKE     LLM_FALLBACK=none                         Nothing to do; optional
App secrets                  MISSING  INTERNAL_TOKEN, MCP_TOKEN, DASH_PASS_HASH not set  Run make secrets

build gate: PASS (exit 0)
```

Rules: statuses are the words READY, FAKE, MISSING, FAILED (no colour needed; colour may be added but never carries meaning alone). Evidence never contains more than the last four characters of a secret. When the gate fails, the last block lists each failure on its own line, for example:

```
demo gate: FAIL (exit 1)
  - AI_MODE must be live (is off)
  - VOICE_MODE must be twilio (is simulated)
  - POST /mcp without auth must return 401 (public URL not set)
  - EB_DATASET_VERSION must be the SE's pinned version (is public-2026-10-10)
  - Twilio balance must be at least $10 (Twilio row is FAKE)
```

## JSON output (`--json`)

```json
{
  "phase": "integrate",
  "ok": false,
  "failures": ["Akamai inference probe must be READY (is MISSING)"],
  "generated_at": "2026-10-10T16:02:11Z",
  "rows": [
    {
      "key": "akamai_inference",
      "name": "Akamai inference",
      "status": "MISSING",
      "probe": "skipped",
      "evidence": "AKAMAI_API_KEY is a placeholder",
      "next_step": "Put the organizers' key in .env (§0.2 T+20)",
      "env": ["AKAMAI_BASE_URL", "AKAMAI_API_KEY", "MODEL_ID"]
    }
  ]
}
```

`rows` always has the eight rows in the order of [data-model.md](../data-model.md). `env` lists names only. `probe` is `ready`, `failed` or `skipped`.

## Module surface (for tests and other scripts)

```python
mask(value: str) -> str                      # "••••" + last 4, or "••••"
is_placeholder(value: str | None) -> bool
scrub(text: str, secrets: Iterable[str]) -> str
load_env(path: Path | None) -> dict[str, str]   # dotenv_values overlaid by os.environ
evaluate(env: dict[str, str], phase: str,
         probe_results: dict[str, ProbeResult] | None = None) -> Report   # pure; no network
run_probes(env, rows_to_probe, timeout) -> dict[str, ProbeResult]        # the only networked function
render_table(report) -> str; render_json(report) -> str
main(argv: list[str] | None = None) -> int                               # returns the exit code
```

`evaluate` with `probe_results` supplied performs no I/O; this is what `tests/test_check_env.py` drives. When `probe_results` is `None`, `main` calls `run_probes` for the rows that need probing (research R5).
