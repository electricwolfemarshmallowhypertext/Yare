# Live Scientific Continuity: Zero-New-Bill Plan

Execution update, November 24: the owner subsequently approved local-only A/B/C
execution and one controller-correction resume. The bounded pilot is now stopped
before D. See [the actual result](SCIENTIFIC_LIVE_PILOT_RESULT.md). Continuity
checks passed; scientific reasoning acceptance did not. The plan below is the
original pre-execution proposal, not a claim that all its criteria passed.

Prepared November 24, 2026. **Not executed; stop for review.** Preserve
`pre-Stanford-HAI` at `3d5a8d8`, the existing architecture, shared ledger and all
spending limits. No publication or change to the public coding demo is proposed.

## Feasible Method and Unresolved Cost Condition

Use the existing machine for local inference, and the existing Cockroach cluster
only after its applicable free allowance and current headroom are confirmed.
This avoids Token Factory, other paid model APIs, AWS, rented GPUs and new cloud
deployments. It does not make electricity or existing subscriptions literally free.

Observed locally without inference: Ollama is installed; its loopback server was
not responding. Public `qwen3:4b` is already cached, with all referenced layers
present at expected sizes (2,497,293,444 bytes total). Its manifest SHA-256 is
`359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`, matching the
public model digest prefix. Weights have not been rehashed or loaded in this task.
A GPU with approximately 32 GiB VRAM is present; compatibility and actual inference
performance remain untested. [Public model](https://ollama.com/library/qwen3:4b).

Ollama supports disabling cloud models/search with `OLLAMA_NO_CLOUD=1`. A future
run must bind loopback only, pin the cached model digest, and fail rather than
fall back to cloud or download another model. No server was started now.
[Local-only configuration](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features).

Cockroach's documented Basic allowance includes 50 million request units and
10 GiB free storage monthly, subject to plan applicability. That is not evidence
of this account's tier, billing terms or remaining allowance. **Zero incremental
database cost is conditional and not yet verified.** Review billing metadata before
any SQL, confirm an existing cost limit/free headroom, and stop if that cannot be
established. Do not silently use paid credits or change billing settings.
[Provider pricing](https://www.cockroachlabs.com/cockroachdb/pricing/).

## Exact Preconditions

1. Owner approves this execution plan, not merely the earlier offline work.
2. Read-only account inspection confirms the existing cluster can accept this
   bounded workload without a new charge. No new cluster or plan migration.
3. Existing runtime credential has SELECT/INSERT for Yare's seven tables; no DDL,
   admin grant, `storage init`, privilege change or schema change in this run.
4. The 19 frozen implementation/data fingerprints still match the checkpoint.
5. Local model layers are hash-verified against the pinned manifest before use;
   local-only server configuration is confirmed. No unrelated services are stopped.
6. Research processes receive only the public brief, approved observations and
   verified handoff projection. No private project, host-folder mount, credentials
   or prior conversation is supplied to an agent. The controller alone accesses DB.

## Independent Sessions, Not Scripted Answers

Run three investigations, each A -> B -> C -> D, using unique task/run IDs.
Same model, fresh process and empty message context per agent: this establishes
session replacement, not agreement among independently developed model families.
Use the fixed brief, not `requests/a.json` or `requests/b.json` as repair hints.

- A requests observed measurements/analysis and emits an unverified interpretation.
- B loads A from Cockroach, checks the exact hashes, and challenges interpretations
  only when supported. Do not manufacture a disagreement to satisfy the scenario.
- C starts after B exits. Its scientific context comes only from the fixed brief
  and verified Cockroach record; it requests a real recomputation by the pinned
  analysis tool and distinguishes calculations from hypotheses.
- Before D, present the three C summaries/receipts for a **new actual operator
  decision**. The offline fixture approval is not standing approval. D records that
  decision and diagnostic recommendations without classifying or scheduling.

Allowed research tools: inspect bounded public observations, run the pinned
descriptive analysis, load the exact parent, and emit the typed evidence record.
No general shell, arbitrary path access, edits to analysis/data, browsing, uploads
or model-supplied tool stdout. Keep raw requests/responses outside the next agent's
context, while retaining them for audit.

The current producer explicitly labels its requests `scripted_fixture`. Running
it with `--storage cockroach` alone is **not** a live-agent test. The execution
needs a thin research-only acquisition adapter: capture the local model response,
validate its typed fields, attach exact request/response hashes and local-provider
metadata, then mark `live_model` only for genuinely captured generations. Reuse
existing compilation/persistence/loading. This adapter is not implemented or
authorized by this planning document; no new product subsystem is required.

## Predeclared Resource Envelope

| Resource | Proposed upper bound / basis |
| --- | --- |
| Local generations | 12 minimum, 24 maximum: at most two per role, three investigations; stop on a second invalid response, no task-specific repair hints |
| Model context/output | 8,192-token context; 2,048 generated-token cap per response; retain actual prompt/evaluation counters and reject truncation |
| Local generated tokens | At most 49,152 under the 24-response cap |
| Inference deadline | 180 seconds per generation; at most 72 minutes inference time, excluding human review; performance is unmeasured |
| Model download | None proposed; cached public model only |
| GPU/RAM | Approximately 4-8 GiB planning allowance for this 4B model/context; not a measured allocation; stop on memory/driver failure rather than rent compute |
| Cloud rows | 12 runs/states/receipts/events/snapshots/artifacts; 81 section vectors in offline shapes, at most 84 for seven sections per state |
| INSERT statements | At most 156: 72 fixed statements plus 84 vector inserts, 12 transactions; no DDL or UPDATE |
| SELECT statements | Budget at most 75 for parent reads, write/read-back verification, final counts, timeline/diff and six predefined search questions |
| Logical JSON writes | Offline shapes imply about 8,574,990 bytes, before vectors, indexes, replication or physical storage overhead; not a billing/RU estimate |
| Local evidence files | Reserve 50 MiB excluding the already cached model; retain every attempt |

The live record size may differ with genuine reasoning. Cap packet-plus-receipt
serialization at 1 MiB per stage and total logical JSON writes at 32 MiB before
persistence; stop if the declared storage/read envelope would be exceeded.
Check free headroom with a conservative allowance (at least 100 MiB storage and
5 million RUs) only if those allowances are applicable and available. These are
safety planning reserves, not measured consumption guarantees. Account-wide
concurrent use must not be ignored. No literal $0 promise before billing review.

The existing Token Factory ledger remains byte-identical at 495/500 calls, USD 5,
2 million tokens. Local inference would be a separately disclosed, zero-API-price
experiment requiring explicit approval; it is not permission to bypass or reset
the paid-provider ledger. No local inference has been performed now.

## Acceptance, Evidence and Stop Rules

After each compile, SELECT the exact record back and verify state, packet, receipt,
data, code and parent associations. Run the independent bundle verifier separately
from the producing process. The supplied verifier is deliberately offline-fixture
specific; a live-evidence variant must also check genuine provider transcripts
before accepting `live_model`, rather than changing a label alone. Preserve actual local-provider model digest, request/
response bodies and hashes, token counters, timings, tool outputs, all attempts,
human decision and row counts scoped exclusively to the 12 new research run IDs.

Report observed DB write/read latency and physical growth separately from logical
JSON estimates. Six fixed search questions are a small retrieval measurement,
not a broad semantic benchmark. Keep numerical results reproducible at declared
tolerance and keep scientific interpretations unverified. Do not infer scientific
correctness, discovery acceleration, deployment capacity or Stanford endorsement.

Stop on unconfirmed free billing, missing privilege/table, hash mismatch, context
leak, truncated output, repeated invalid response, absent human decision, timeout,
budget-envelope exhaustion, or inability to retain genuine model evidence. No
paid fallback and no replacing a failed run with scripted reasoning.

No live command is presented as ready to run: the small acquisition adapter and
account-cost preflight need review first. Existing scripted, database and bundle
verification commands remain documented separately. Stop for owner review.
