# Public Model Budget Gate

Status: **default-off; not enabled or approved for public use.** A Git push may create a disabled preview deployment; no production rollout is approved. `/api/model-preview` is a bounded Nemotron Nano completion endpoint, not a coding agent. It cannot edit files, run tests, or create a Yare handoff.

The handler returns 503 unless `YARE_PUBLIC_MODEL_ENABLED=true`. Enabling it also requires a server-side Nebius key, CockroachDB URL and CA certificate, an allowed model ID, a budget ID, and explicit input/output price ceilings. The browser receives none of those credentials. The database must contain an unblocked budget row; `site/schema/public-model-budget.sql` creates tables but deliberately creates no budget row. The separately seeded shared-ledger row is blocked.

Each accepted request is bounded to 4,096 UTF-8 prompt bytes and 512 output tokens. Before a Token Factory call, one CockroachDB transaction conditionally charges a conservative cost and token bound against the budget row and inserts a call reservation. Concurrent requests contend on the same row. Missing budget, exhausted calls, exhausted tokens, insufficient money, or a failed transaction returns 503 before provider access. Observed usage is recorded after a response, but the global counter keeps the full reservation. Unknown or out-of-bound usage retains the reservation and blocks the budget.

**Do not enable this endpoint yet.** The private JSON ledger was unchanged at 412/500 calls, 1,383,991/2,000,000 charged tokens, and $0.25332318 conservatively estimated under the $5 cap when the blocked row was seeded. Before any activation, recheck the ledger against the Cockroach row, stop independent writes to the JSON ledger or migrate them to the same atomic gate, verify current provider prices and the configured ceilings, and obtain explicit approval for the UI, hosting, abuse controls, and spending policy. The screenshot's $0.23 billed total is a different accounting measure and is not a replacement for the reservation ledger.

Read-only reconciliation check: `node site/scripts/public-budget-dry-run.js <ignored-ledger-path>`. On October 8, 2026 it reported 412 calls, 1,383,991 tokens, exact estimated charge $0.25332318, and a conservative micro-dollar starting charge of 253324 ($0.253324). This command does not change the ledger or create a DB budget row. The actual counters must be rechecked before any activation.

The authorized blocked-seed command is `node site/scripts/public-budget-seed-blocked.js <ignored-ledger-path>`. It requires server-side `YARE_PUBLIC_BUDGET_ID`, `YARE_DATABASE_URL`, and `YARE_DATABASE_CA_PEM`, refuses to run while `YARE_PUBLIC_MODEL_ENABLED=true`, inserts only a blocked row, and refuses to overwrite an existing budget ID. On October 8, 2026, it seeded `yare-nebius-upgrade-shared` from the unchanged private ledger; a before/after ledger hash matched. A DB readback confirmed `blocked=true`, 412/500 calls, 1,383,991/2,000,000 tokens, and 253324/5000000 micro-dollars charged/limit. A real DB-backed endpoint guard check returned 503 with no provider call or counter change. Do not rerun the seed or unblock the row without reconciling any subsequent ledger activity and obtaining approval. A blocked row alone cannot authorize public model calls.

Required server configuration when activation is approved:

```text
YARE_PUBLIC_MODEL_ENABLED=true
YARE_PUBLIC_BUDGET_ID=<approved Cockroach budget row>
YARE_PUBLIC_MODEL_ID=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
YARE_PUBLIC_INPUT_CEILING_USD_PER_MILLION=<verified conservative ceiling>
YARE_PUBLIC_OUTPUT_CEILING_USD_PER_MILLION=<verified conservative ceiling>
YARE_DATABASE_URL=<private Cockroach connection string>
YARE_DATABASE_CA_PEM=<trusted Cockroach CA certificate>
NEBIUS_API_KEY=<private Token Factory key>
```

The endpoint is not linked from site navigation or the upgrade preview page. It makes no provider request while disabled. A server-side cap limits total reserved spending but does not prevent anonymous visitors from exhausting the allowance; any public rollout also needs an approved abuse-control policy. A future date of availability cannot be guaranteed by this gate alone.

Local fixture verification, without external calls:

```powershell
node --test site/tests/public-model-budget.test.js
node --check site/api/model-preview.js
```

Real Cockroach smoke on October 8, 2026: **PASS**. `node site/tests/public-model-budget.db-smoke.js` created the schema, inserted temporary one-call budgets, attempted two reservations concurrently, and observed exactly one committed reservation and one rejection. Marking the accepted call's usage unknown kept its reservation charged, blocked that budget, and rejected another reservation. With a separate temporary budget, the endpoint accepted one request, recorded observed usage from a stubbed provider response, and rejected a second request before calling the stub again. A third temporary row confirmed blocked seeding preserves starting counters and refuses overwrite. All test rows were removed. It made no Token Factory request and did not enable the endpoint. This proves the atomic one-row cap, fail-closed status, endpoint reservation path, and blocked seed on that connection; it does not prove a public rollout or future provider pricing.
