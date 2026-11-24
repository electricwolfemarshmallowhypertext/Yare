# Yare Handoff Integrity Bench

Yare was tested on messy AI coding handoffs with conflicting agent claims, changed files, unresolved approvals, and receipts.

The local bench asserts the compiled sample handoff, source inputs, state-hash repeatability, and receipt integrity. With services configured, it also compares CockroachDB records and S3 object bodies against that same output.

Separate recorded checks cover these capabilities:

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
4. Agent readability: separate Claude Code, Codex, and Cursor MCP sessions are documented below. This script does not run those clients.
5. Regression check: two identical compiles must have equal state hashes and distinct, valid timestamped receipts. Task-filtered timeline and diff commands are also run when CockroachDB is configured; their command output is not a new transition test.

## Reproduce Locally

```powershell
.\scripts\proof-bench.ps1
```

This compiles the samples twice. It fails if changed files, unsupported claims, contradictions, approval items, open loops, or the next action differ from the expected sample handoff. None of the sample claims has linked execution evidence, so none may enter confirmed facts.

The script recalculates state and receipt hashes, checks the original source artifacts, asserts state-hash stability, and checks that the two receipt hashes differ. Timestamped receipts are not deterministic bytes. Skipped services do not count as passing checks.

## Reproduce With Live Services

CockroachDB memory:

```powershell
$env:YARE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
.\scripts\proof-bench.ps1
```

Or pass it to the script's process:

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

The script does not print connection strings. If live env vars are missing, live CockroachDB and S3 checks are reported as skipped, not failed. A configured service returning mismatched data fails the bench.

CockroachDB read-back compares the run packet, current-state snapshot, source artifacts and their hashes, receipt, and stored vector section texts. It also checks the real vector index definition, requires EXPLAIN to select that index, and executes the nearest-neighbor query. These checks do not establish general semantic retrieval quality. S3 read-back compares all three downloaded object bodies with the exact local files after each compile.

The existing S3 keys are based on the state hash. Repeating that state replaces `receipt.jsonl` at the same key with the new receipt. This is the current state's proof export, not an immutable archive of every receipt; CockroachDB and local receipt files retain distinct receipt records.

CockroachDB must be enabled with `YARE_DATABASE_URL` in the current shell. The database can exist and still be skipped if that env var is not set for the process running the bench.

S3 must be enabled with both `YARE_S3_BUCKET` and usable AWS credentials in the current shell or default boto3 credential chain. If the bucket is set but AWS credentials are unavailable, the bench reports S3 as skipped instead of failing the compile.

## Proof Matrix

These are separate historical integration checks, not one combined end-to-end run. PASS means the linked result records a pass within its stated scope. The script does not reproduce MCP client sessions or establish autonomous coding performance.

| Proof | Result | Evidence |
|---|---|---|
| Real CockroachDB write/read | PASS | [COCKROACH_SMOKE_RESULT.md](COCKROACH_SMOKE_RESULT.md) |
| Real S3 receipt archive | PASS | [S3_SMOKE_RESULT.md](S3_SMOKE_RESULT.md) |
| Claude Code MCP read | PASS | [MCP_SMOKE_RESULT.md](MCP_SMOKE_RESULT.md) |
| Codex MCP read | PASS | [CODEX_MCP_SMOKE_RESULT.md](CODEX_MCP_SMOKE_RESULT.md) |
| Cursor MCP read | PASS | [CURSOR_MCP_SMOKE_RESULT.md](CURSOR_MCP_SMOKE_RESULT.md) |
| Vector memory search | PASS | [VECTOR_SMOKE_RESULT.md](VECTOR_SMOKE_RESULT.md) |
| Timeline diff | PASS | [MEMORY_TIMELINE_RESULT.md](MEMORY_TIMELINE_RESULT.md) |
| Deterministic state hash and receipt integrity | See rerun result | [HANDOFF_ASSERTIONS_RESULT.md](HANDOFF_ASSERTIONS_RESULT.md) |

Current assertion rerun: [HANDOFF_ASSERTIONS_RESULT.md](HANDOFF_ASSERTIONS_RESULT.md). Historical command-runner result: [HANDOFF_INTEGRITY_BENCH_RESULT.md](HANDOFF_INTEGRITY_BENCH_RESULT.md).

## Public Claim

The bench checks the compiled output and configured storage read-back. The linked historical reports document other integrations separately. Hash checks detect inconsistent saved contents; they do not authenticate who ran a test. Imported execution evidence requires a trusted runner.
