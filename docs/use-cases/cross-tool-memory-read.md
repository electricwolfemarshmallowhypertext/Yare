# Cross-Tool Memory Read

Use case:
Let different agent clients inspect the same stored work state.

Who it is for:
Teams switching among Claude Code, Codex, and Cursor.

What breaks today:
Each client has its own conversation context, so the next agent may reconstruct the work differently.

Why Yare fits:
Yare compiles one current state in CockroachDB that clients can query through CockroachDB Managed MCP.

What Yare stores:
- task and current-state hash
- verified and unverified claims
- contradictions
- approval items
- receipts
- next clean action

What Roach makes durable:
CockroachDB is the shared source for the compiled state and receipts.

What the user sees:
The same recorded handoff can be reported from more than one agent client.

When they use it:
When changing tools or asking another agent to review prior work.

Why it matters:
The handoff is not trapped in the first client's chat history.

Demo proof:
Claude Code, Codex, and Cursor each queried Yare's CockroachDB memory through Managed MCP and reported the recorded handoff. See `docs/MCP_SMOKE_RESULT.md`, `docs/CODEX_MCP_SMOKE_RESULT.md`, and `docs/CURSOR_MCP_SMOKE_RESULT.md`.

One-line pitch:
Claude Code, Codex, and Cursor can read the same CockroachDB handoff through Managed MCP.
