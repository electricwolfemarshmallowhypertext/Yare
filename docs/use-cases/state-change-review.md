# State Change Review

Use case:
See how the compiled work state changed between runs.

Who it is for:
Engineers reviewing whether new work resolved or introduced open issues.

What breaks today:
A latest-state summary does not explain which facts, claims, contradictions, or next actions changed.

Why Yare fits:
The memory timeline lists stored states, and the latest-state diff compares the two newest snapshots.

What Yare stores:
- current-state hashes and timestamps
- task and run ID
- receipt hashes
- facts and unresolved claims
- contradictions and approval items
- next clean action

What Roach makes durable:
CockroachDB retains the snapshots that the timeline and diff read.

What the user sees:
A previous-to-latest comparison with new truths, unresolved claims, cleared contradictions, and any changed next action.

When they use it:
After a new compile, before review, or when returning to a task after several runs.

Why it matters:
Reviewers can see what changed in the memory, not only the latest summary.

Demo proof:
The live CockroachDB smoke ran `memory timeline` and `memory diff --latest` against stored current states. See `docs/MEMORY_TIMELINE_RESULT.md`.

One-line pitch:
Compare stored states to see new facts, unresolved claims, cleared contradictions, and changed next actions.
