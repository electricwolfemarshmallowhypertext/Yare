# Devtool Founders / AI Agencies

Use case:
Multi-client agent handoff

Who it is for:
Devtool founders and AI agencies running agent work across many repos, clients, demos, and internal tools.

What breaks today:
Agent work gets spread across client chats, local terminals, Cursor sessions, Codex runs, Claude Code runs, CI output, and hand-written notes. The agency has to explain what happened without a clean record.

Why Yare fits:
Yare turns each agent run into a durable handoff that can be reviewed later by the founder, client, or next agent.

What Yare stores:
- task
- changed files
- verified facts
- unverified claims
- contradictions
- client approval items
- open loops
- receipts
- next clean action

What Roach makes durable:
CockroachDB keeps the project memory queryable across clients, agents, tools, and handoff sessions.

What the user sees:
A client-safe handoff:
"What changed, what is proven, what needs approval, and what the next agent or engineer should do."

When they use it:
- after a client agent session
- before sending a client update
- before handing work to another contractor
- before demo day
- before merge or deploy
- when switching between client projects

Why it matters:
Agencies cannot run on vibes. They need proof of work, clean handoffs, and fewer "what did the AI actually do?" moments.

Demo proof:
Yare persists working memory to CockroachDB and lets Claude Code, Codex, and Cursor read the same handoff through MCP.

One-line pitch:
Yare gives devtool founders and AI agencies a durable work record for every agent-run client project.
