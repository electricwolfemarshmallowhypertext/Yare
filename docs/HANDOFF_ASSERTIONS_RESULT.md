# Handoff Assertion Rerun

Date: 2026-10-09

The sample compile and read-back assertions passed. This is a sample integrity test, not an autonomous coding benchmark or a combined MCP/S3 certification.

## Commands

Local, without live service variables:

```powershell
.\scripts\proof-bench.ps1
```

Live CockroachDB, with the existing connection loaded into the process environment:

```powershell
$env:YARE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
.\scripts\proof-bench.ps1
```

No connection credentials are included here. No models or sandbox coding runs were invoked.

## Checked Output

| Assertion | Observed result |
| --- | --- |
| Expected changed files, unverified claims, contradiction, approvals, open loops, next action | PASS |
| Unsupported sample labels do not become confirmed facts | PASS: zero confirmed facts, four unverified claims |
| Compiled artifacts match the sample input files | PASS |
| State and receipt hashes recalculate correctly | PASS |
| Two identical compiles preserve the state hash | PASS |
| Two timestamped receipts are distinct | PASS |
| Cockroach run packet and source hashes match | PASS |
| Cockroach immutable state packet matches | PASS |
| All three stored source artifacts match | PASS |
| Both exact stored receipts match | PASS |
| Stored vector section texts match the compiled sections | PASS |
| Real vector index exists and is selected by EXPLAIN | PASS |
| Nearest-neighbor query executes and returns bounded, finite-distance rows | PASS |
| S3 object byte comparisons | NOT RUN: no bucket configured |
| MCP client reads | NOT RUN: separate sessions required |

Observed live state hash:

```text
4c6c3344ff76db858595fdb3f7f39be01a94d1c43ee4ba1621cd99e9acffcdf2
```

First receipt hash:

```text
9334ab0bbfa80e897182e4b8839ff0a0c72ab50edf4429a8267161cf852fa9f3
```

Repeat receipt hash:

```text
24aa7a0cc297dcce0a2aa4a006ba6aaec4ec144f36b73bf81e58cf5d765909f4
```

The state hash includes the captured repository state; later source or git-state changes may change it. Repeatability here means the inputs and captured context did not change between the two compiles, not a permanent universal hash.

## Scope

Task-filtered timeline and diff commands also returned successfully. They were not used to claim a new agent completion or to resolve an unsupported claim. Search returned existing approval and next-action sections; those results belong to historical snapshots, not necessarily the new state.

The S3 byte-comparison implementation has fixture coverage, including deliberate mismatched object bodies. No new real S3 check was performed. Vector index use was checked separately from section persistence: EXPLAIN included a vector search over `yare_memory_vectors_embedding_idx`, and the same nearest-neighbor SQL executed successfully. This establishes real index/query operation, not general semantic retrieval quality.
