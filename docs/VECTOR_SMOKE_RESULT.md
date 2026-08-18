# CockroachDB Vector Smoke Result

Status: PASS

Date: 2026-07-09

## Scope

This smoke test verified Yare vector memory writes and vector search against the live CockroachDB cluster through `YARE_DATABASE_URL`.

No secrets are included.

## Database URL

Redacted DB URL:

```text
postgresql://REDACTED@yare-roach-28678.j77.aws-us-east-2.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full
```

## Commands

```powershell
python -m cli.yare storage init
```

Output:

```text
storage: initialized
tables: yare_runs, yare_lead_artifacts, yare_current_states, yare_receipts, yare_memory_vectors
```

```powershell
python -m cli.yare lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
```

Output:

```text
current_state_json: .sticky/current-state.json
current_state_md: .sticky/current-state.md
deterministic_hash: 3e17416e734594685d1aa33a5502c0a4d0079595273e1e95b181e7b8a56d8a8a
receipt: .sticky/receipts/20260709T224416664743Z.jsonl
receipt_hash: 40510d9d51ae76672272f21bc8e8d663a3739f99b87310b9f2ab29f83ccd2d2f
```

```powershell
python -m cli.yare memory search --query "what still needs human review?" --limit 3
```

Output:

```text
result: 1
section: what is unverified
distance: 0.658118
current_state_hash: 3e17416e734594685d1aa33a5502c0a4d0079595273e1e95b181e7b8a56d8a8a
text:
All receipt tests passed in CI

result: 2
section: what is true
distance: 0.876909
current_state_hash: 3e17416e734594685d1aa33a5502c0a4d0079595273e1e95b181e7b8a56d8a8a
text:
Endpoint returns latest receipt
README includes Yare handoff section
Receipt includes git dirty status

result: 3
section: next clean action
distance: 0.909091
current_state_hash: 3e17416e734594685d1aa33a5502c0a4d0079595273e1e95b181e7b8a56d8a8a
text:
Resolve human-approval items before the next run.
```

## Result

Real CockroachDB vector smoke passed.

The smoke created/initialized `yare_memory_vectors`, persisted vectors after compile, and returned vector search results from CockroachDB.
