# Restart After a Partial Run

Use case:
Continue a coding task after the first agent stops with work unfinished.

Who it is for:
Teams handing an incomplete agent run to a fresh agent or engineer.

What breaks today:
The next worker may see only a confident summary, not the partial code and actual failing test output.

Why Yare fits:
Yare stores the partial artifact, compiled state, and receipt so a fresh worker can assess the real result.

What Yare stores:
- task and code artifact
- actual test output
- unverified claims
- unresolved work
- next clean action
- receipt hashes

What Roach makes durable:
CockroachDB preserves the handoff between separate agent sessions.

What the user sees:
The first run's passing targeted tests and failing full suite, followed by the second run's final result.

When they use it:
When an agent stops, a sandbox is replaced, or another agent takes over.

Why it matters:
The next worker can start from stored evidence instead of guessing what the first worker finished.

Demo proof:
In one isolated coding task, A passed four targeted tests but left two full-suite failures. Fresh B read A's CockroachDB handoff, fixed the remaining issue, and passed all six tests. See `docs/NEMOTRON_RESUMED_HANDOFF_RESULT.md`.

One-line pitch:
Resume a coding task after the first agent stops, using stored code and actual test output.
