# AI Coding Teams

Use case:
AI coding handoffs

Who it is for:
Teams using Claude Code, Codex, Cursor, CI jobs, scripts, and human engineers on the same repo.

What breaks today:
The work gets scattered. One agent changes files. Another claims tests passed. CI says something else. A human comes back later and has to reconstruct the truth from chats, logs, diffs, and guesses.

Why Yare fits:
Yare turns those scattered runs into one verified working-memory handoff.

What Yare stores:
- what changed
- what is true
- what is unverified
- contradictions
- human approval items
- open loops
- next clean action
- receipts

What Roach makes durable:
The current-state memory lives in CockroachDB, so it can be read later by another agent, another tool, or another teammate.

What the user sees:
A plain handoff:
"Here is what happened. Here is what is verified. Here is what still needs review. Here is what to do next."

When they use it:
- before a new agent starts work
- before a PR review
- after a long AI coding session
- before release
- after CI or tests change state
- when switching from Claude to Codex to Cursor

Why it matters:
The team stops treating AI output like disposable chat history. The repo gets a memory trail that survives tool switching, model switching, and human context loss.

Demo proof:
Claude Code, Codex, and Cursor used MCP to read Yare's CockroachDB memory and report the same repo handoff.

One-line pitch:
Yare gives AI coding teams a durable handoff so every agent knows what changed, what is true, and what needs human review.
