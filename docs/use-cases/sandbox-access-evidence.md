# Sandbox Access Evidence

Use case:
Review an agent's access decision alongside its code and test evidence.

Who it is for:
Engineers evaluating a permission-scoped coding handoff.

What breaks today:
An agent may report an access failure without preserving the policy result with its work receipt.

Why Yare fits:
Yare can record OpenShell's access result in a compiled handoff and receipt.

What Yare stores:
- stated agent action
- allowed or denied access result
- code and test evidence
- receipt hash
- next clean action

What Roach makes durable:
CockroachDB retains the compiled handoff and access-bearing receipt.

What the user sees:
The recorded access result beside the partial and completed coding runs.

When they use it:
After separate agents work under different OpenShell policies.

Why it matters:
The access decision remains reviewable with the work it affected. OpenShell enforces the boundary; Yare records it.

Demo proof:
In the isolated A/B coding run, A read a sandboxed source snapshot, B was denied access to that same snapshot, and B still completed its separate working copy. See `docs/NEMOTRON_BOUNDARY_RESULT.md`.

One-line pitch:
Review recorded OpenShell access decisions with the agent handoff and receipts.
