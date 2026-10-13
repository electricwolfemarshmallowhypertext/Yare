# Yare Technical Architecture

Yare compiles agent work records into durable handoffs. CockroachDB is the primary system of record. The coding producer, sandbox enforcement, and public evidence viewer are separate components.

## Data Flow

```text
Coding producer or imported tool output
-> Lead Artifact: changes, claims, test evidence, unfinished work
-> CLI validation and compile
-> current state, source packet, and receipt
-> CockroachDB storage
-> verified handoff load
-> next coding agent
```

Local JSON exports are an optional fallback. S3 can archive proof artifacts when configured; it is not required for the CockroachDB handoff.

## Artifact Compilation and Evidence

`cli/yare.py` validates Lead Artifacts and compiles changed files, supported facts, unverified claims, contradictions, approval items, open loops, and next action.

A verified claim requires linked test evidence or a recorded human review for that claim. The coding controller records command output and exit codes. Imported evidence must come from a trusted runner or reviewer: the compiler checks the supplied record, not the identity of its author, and does not rerun arbitrary artifact commands. Disputed claims are excluded from confirmed facts. An omitted claim is removed, not automatically resolved.

See [Handoff Integrity](HANDOFF_INTEGRITY.md) for the evidence shape and loader checks.

## CockroachDB Storage and History

`cli/storage.py` stores runs, Lead Artifacts, current states, and receipts in `yare_runs`, `yare_lead_artifacts`, `yare_current_states`, and `yare_receipts`. Compiled packets preserve source artifacts.

`yare_run_snapshots` preserves run/state snapshots. `yare_events` records compile events so repeated states remain visible in history. Timeline selects recent events and displays them chronologically. Timeline and diff support task filtering.

Schema setup belongs to `python -m cli.yare storage init`, not each runtime write. Runtime credentials can use narrower read/insert permissions than schema administration. Managed MCP provides a separate agent-client read path; free-form SQL reads do not themselves perform the producer's handoff verification.

## State and Receipt Integrity

The `work-state.v2` state hash covers the task, current state, and normalized artifact content. Operational metadata such as checkout paths and git state is excluded from that hash. Receipts separately bind execution metadata and packet integrity. Timestamped receipts can differ even when the state hash is stable.

`producers/handoff.py` loads the selected state, packet, source code, and matching receipt from CockroachDB. It checks their hashes and associations before B uses the code. Missing or mismatched records stop the handoff. New B artifacts can identify the exact parent handoff; that field is not retroactively added to historical runs.

Hashes detect record changes; they do not establish author trust or coding correctness.

## Memory Search

`yare_memory_vectors` stores section text and deterministic local hashed text vectors with a CockroachDB vector index. Search uses cosine distance (`<=>`) together with word and section matching, and removes duplicate results. No external embedding service is required.

This is hybrid retrieval, not a learned language embedding model. Known review, file-change, and unfinished-work queries have been checked against stored memory. Those checks do not establish broad semantic search accuracy. See [Vector Indexing](VECTOR_INDEXING.md).

## Coding Producer and Sandbox Boundary

The separate producer calls NVIDIA Nemotron through Nebius Token Factory, inspects task files, applies edits, runs tests, and records observed results. OpenShell enforces sandbox permissions; Yare records work and access evidence. The shared spending ledger reserves calls before execution and preserves unresolved usage reservations. `yare run` prints launch instructions; it does not execute an agent.

In the [recorded A/B task](NEMOTRON_BOUNDARY_RESULT.md), A passed four focused tests but left two full-suite failures. Fresh B loaded A's stored handoff, completed the normalization fix, and passed all six tests. OpenShell allowed A and denied B access to the same source snapshot inside the sandboxes while B used a separate working copy. This is one isolated task and a sandbox snapshot boundary, not a broad autonomous benchmark or a process/network boundary proof.

See [Provider Routing](NEBIUS_PROVIDER_ROUTING.md) for setup and integration details.

## Public Read-Only Demo

`site/demo.html` and `site/demo.js` fetch `/api/verified-handoff`. The Node endpoint uses `pg` and server-side `YARE_DATABASE_URL` to read two approved CockroachDB records. It verifies state, packet, source, and receipt integrity before returning an allowlisted public projection. Credentials remain server-side.

The page presents a plain-English summary with expandable technical evidence and a JSON download. Loading it does not run a model, edit code, or write database records. Paid public execution remains disabled by default.

The recorded artifacts were recompiled after the coding run to bind access evidence into receipts; those database timestamps are not coding-run durations. For A's historical claim that all full-suite tests passed, the API exposes an evidence-based correction to contradicted because the saved full-suite output reports failures. The original handoff is retained separately. Exported hashes refer to the original stored records, not the corrected display view. The projected JSON alone does not contain every input needed to recompute those hashes independently.

## Optional Archive and Scope

`cli/archive.py` skips S3 when `YARE_S3_BUCKET` is unset. The [historical S3 result](S3_SMOKE_RESULT.md) documents an earlier archive check; it does not establish fresh read-back access. S3 availability does not gate the demonstrated CockroachDB coding handoff.

Legacy services retained in the repository are not the supported CLI, producer, or static demo architecture described here. Historical result documents retain their dates and scope; they should not be combined into a claim that every integration ran together in one execution.
