# Yare Handoff Integrity Bench

Yare was tested on messy AI coding handoffs with conflicting agent claims, changed files, unresolved approvals, and receipts.

The bench verifies that Yare can:

- compile scattered agent output into one current-state handoff
- detect contradictions
- preserve receipts
- persist memory in CockroachDB
- archive proof artifacts to S3
- expose the same handoff through MCP
- show how work-state changed over time

## Bench Inputs

The public bench uses the existing sample lead artifacts:

- `examples/lead-artifacts/run-codex.jsonl`
- `examples/lead-artifacts/run-claude.json`
- `examples/lead-artifacts/run-gemini.jsonl`

These artifacts model Claude/Codex/Cursor-style work with changed files, conflicting claims, missing verification, CI/test claims, dirty-state receipts, and human approval items.

## What The Bench Tests

1. Input chaos: scattered agent output, contradictory claims, missing verification, changed files, and human approval items.
2. Yare compile: validation, current-state generation, contradiction handling, deterministic hashes, and receipt writing.
3. Durability: CockroachDB persistence, S3 proof archive, and reloadable current-state memory.
4. Agent readability: Claude Code, Codex, and Cursor reading the same CockroachDB-backed handoff through MCP.
5. Regression check: rerunning the bench and comparing previous to latest state with the memory timeline diff.

## Reproduce Locally

```powershell
.\scripts\proof-bench.ps1
```

This runs the sample lead compile and prints the current-state hash, receipt path, and receipt hash.

## Reproduce With Live Services

CockroachDB memory:

```powershell
$env:YARE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
.\scripts\proof-bench.ps1
```

Or pass it for one run without permanently setting the env var:

```powershell
.\scripts\proof-bench.ps1 -DatabaseUrl "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
```

S3 proof archive:

```powershell
$env:YARE_S3_BUCKET = "your-bucket"
$env:YARE_S3_PREFIX = "yare/"
.\scripts\proof-bench.ps1
```

Or pass the archive target for one run:

```powershell
.\scripts\proof-bench.ps1 -S3Bucket "your-bucket" -S3Prefix "yare/"
```

The script does not print secrets. If live env vars are missing, live CockroachDB and S3 checks are reported as skipped, not failed.

CockroachDB must be enabled with `YARE_DATABASE_URL` in the current shell. The database can exist and still be skipped if that env var is not set for the process running the bench.

S3 must be enabled with both `YARE_S3_BUCKET` and usable AWS credentials in the current shell or default boto3 credential chain. If the bucket is set but AWS credentials are unavailable, the bench reports S3 as skipped instead of failing the compile.

## Proof Matrix

| Proof | Result | Evidence |
|---|---|---|
| Real CockroachDB write/read | PASS | [COCKROACH_SMOKE_RESULT.md](COCKROACH_SMOKE_RESULT.md) |
| Real S3 receipt archive | PASS | [S3_SMOKE_RESULT.md](S3_SMOKE_RESULT.md) |
| Claude Code MCP read | PASS | [MCP_SMOKE_RESULT.md](MCP_SMOKE_RESULT.md) |
| Codex MCP read | PASS | [CODEX_MCP_SMOKE_RESULT.md](CODEX_MCP_SMOKE_RESULT.md) |
| Cursor MCP read | PASS | [CURSOR_MCP_SMOKE_RESULT.md](CURSOR_MCP_SMOKE_RESULT.md) |
| Vector memory search | PASS | [VECTOR_SMOKE_RESULT.md](VECTOR_SMOKE_RESULT.md) |
| Timeline diff | PASS | [MEMORY_TIMELINE_RESULT.md](MEMORY_TIMELINE_RESULT.md) |
| Deterministic receipt/hash proof | PASS | [REAL_USE_CASE_RESULT.md](REAL_USE_CASE_RESULT.md), [COCKROACH_SMOKE_RESULT.md](COCKROACH_SMOKE_RESULT.md) |

Latest bench rerun notes: [HANDOFF_INTEGRITY_BENCH_RESULT.md](HANDOFF_INTEGRITY_BENCH_RESULT.md)

## Public Claim

The strongest proof is not that the demo loads data. It is that the same messy handoff can be compiled, stored, archived, queried, searched, diffed, and independently read through multiple agent clients with receipts and hashes.
