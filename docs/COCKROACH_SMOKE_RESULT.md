# Real CockroachDB Smoke Result

Date: 2026-07-09

## Scope

This smoke test verified Yare durable memory persistence against a real CockroachDB connection.

Credentials and connection details are redacted. Do not commit secrets.

## Evidence

- CA cert downloaded to `$env:APPDATA\postgresql\root.crt`
- `YARE_DATABASE_URL` set locally with credentials redacted
- `python -m cli.yare storage init`: PASS
- `python -m cli.yare lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl`: PASS

## Compile Output

- `current_state_json`: `.sticky/current-state.json`
- `current_state_md`: `.sticky/current-state.md`
- `deterministic_hash`: `94776858ca61b6e768852437aed02471a23ee0e6cb0a13b7df5a4d9aed7899c9`
- `receipt`: `.sticky/receipts/20260709T123205193482Z.jsonl`
- `receipt_hash`: `9ee44a117505047e6e854176a213f3d8fcce2331487367eeb92aee4944b2df30`

## Row Counts

| Table | Rows |
|---|---:|
| `yare_runs` | 1 |
| `yare_lead_artifacts` | 3 |
| `yare_current_states` | 1 |
| `yare_receipts` | 1 |

## Result

Real CockroachDB smoke test passed.

No Cockroach SQL compatibility issues were found.
