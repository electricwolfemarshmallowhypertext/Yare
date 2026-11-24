# Contradiction and Approval Review

Use case:
Review conflicting agent claims and work that needs a human decision.

Who it is for:
Engineers and reviewers deciding whether an agent-produced change can proceed.

What breaks today:
One run reports a fact that another disputes, while approval requests get buried in separate logs.

Why Yare fits:
The compiled current state lists contradictions and human approval items separately from verified facts.

What Yare stores:
- verified and unverified claims
- contradictions
- human approval items
- receipts
- next clean action

What Roach makes durable:
CockroachDB keeps that review state available after the original run ends.

What the user sees:
A handoff that says what conflicts, what needs approval, and what to check next.

When they use it:
Before another agent continues, a PR is reviewed, or a release decision is made.

Why it matters:
A contradiction is not silently promoted to a fact, and an approval item is not mistaken for completed work.

Demo proof:
The recorded multi-agent handoff contains a contradiction and human approval items; the current-state and receipt records were read through CockroachDB MCP. See `docs/REAL_USE_CASE_RESULT.md` and `docs/MCP_SMOKE_RESULT.md`.

One-line pitch:
See conflicting claims and pending human approvals together before deciding what can proceed.
