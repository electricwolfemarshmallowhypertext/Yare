# Real Use Case: Coding Agent Handoff

This demo shows Yare helping a new coding agent take over after prior AI runs.

Yare compiles sample Lead Artifacts, persists the verified current state to CockroachDB, then reads that saved memory back and prints a plain handoff:

- what changed
- what is true
- what is unverified
- contradictions
- next clean action

No secrets are committed. `YARE_DATABASE_URL` must be set locally before running the demo.

## Command

```powershell
$env:YARE_DATABASE_URL = "postgresql://<user>:<redacted>@<cluster-host>:26257/defaultdb?sslmode=verify-full"
.\scripts\demo-real-use-case.ps1
```

For a local insecure CockroachDB node, use:

```powershell
$env:YARE_DATABASE_URL = "postgresql://root@localhost:26257/defaultdb?sslmode=disable"
.\scripts\demo-real-use-case.ps1
```

The script runs:

```powershell
python -m cli.yare storage init
python -m cli.yare lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
```

Then it reads the saved current state back from CockroachDB and prints the handoff.

## Expected Output

```text
storage: initialized
tables: yare_runs, yare_lead_artifacts, yare_current_states, yare_receipts
current_state_json: .sticky/current-state.json
current_state_md: .sticky/current-state.md
deterministic_hash: <hash>
receipt: .sticky/receipts/<timestamp>.jsonl
receipt_hash: <hash>

# Yare Current-State Handoff

Task: compile ai work lead state
Current State Hash: <hash>

## What Changed
- README.md
- apps/api/src/memory/server.py
- cli/yare.py

## What Is True
- Endpoint returns latest receipt
- README includes AI Work Lead section

## What Is Unverified
- All receipt tests passed in CI

## Contradictions
- Receipt includes git dirty status

## Next Clean Action
- Resolve human-approval items before the next run.
```

## Why This Matters

The next coding agent does not need to infer state from scattered prior runs. It can read the Cockroach-backed Yare memory and immediately see what happened, what is verified, what is unresolved, and what to do next.
