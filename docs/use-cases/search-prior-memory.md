# Search Prior Memory

Use case:
Find a relevant section from an earlier compiled handoff.

Who it is for:
Agents and engineers returning to a task with stored work history.

What breaks today:
The needed unresolved claim or approval item is buried in an older state record.

Why Yare fits:
The `memory search` command queries sections stored in CockroachDB's vector index.

What Yare stores:
- section name and source text
- current-state hash
- embedding vector
- run ID

What Roach makes durable:
CockroachDB stores and indexes the memory sections for later queries.

What the user sees:
Matching section names, distances, state hashes, and source text.

When they use it:
When searching for a prior decision, unresolved issue, or next action.

Why it matters:
The next worker can locate recorded context without rereading every handoff.

Demo proof:
A real CockroachDB vector index and query returned stored memory sections. See `docs/VECTOR_SMOKE_RESULT.md`.

One-line pitch:
Search prior handoff sections through CockroachDB's vector index.
