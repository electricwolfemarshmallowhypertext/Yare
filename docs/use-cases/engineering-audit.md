# Engineering Audit

Use case:
Agent-written work audit

Who it is for:
Engineering teams reviewing code, tests, docs, and repo changes produced by AI agents.

What breaks today:
Agents say work is done, but reviewers still have to dig through chats, diffs, logs, CI output, and partial receipts to know what actually happened.

Why Yare fits:
Yare gives reviewers one verified handoff instead of scattered agent claims.

What Yare stores:
- files changed
- claims made by agents
- verified facts
- unverified claims
- contradictions
- human approval items
- receipts
- next clean action

What Roach makes durable:
CockroachDB keeps the audit record available across runs, tools, agents, and review sessions.

What the user sees:
A plain audit view:
"What changed, what was proven, what is still risky, and what needs review."

When they use it:
- before PR review
- before merge
- after CI changes
- after a failed agent run
- during release review
- when investigating bad AI-written work

Why it matters:
Reviewers stop trusting agent summaries blindly. They get a durable proof trail.

Demo proof:
Claude Code, Codex, and Cursor queried Yare's CockroachDB memory through MCP and reported the same state.

One-line pitch:
Yare helps engineering teams audit agent-written work before it becomes production risk.
