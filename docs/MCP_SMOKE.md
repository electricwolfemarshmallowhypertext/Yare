# CockroachDB Managed MCP Smoke Test

This smoke test proves an agent can inspect Yare's Cockroach-backed memory through CockroachDB Managed MCP, not through Yare's normal database code.

Do not commit MCP config snippets, service account keys, OAuth tokens, or connection secrets.

## Source

Cockroach Labs describes Managed MCP as a CockroachDB Cloud-hosted MCP endpoint for AI agents. The Cloud Console provides a configuration snippet that can be copied into MCP clients such as Claude Code, Cursor, or VS Code. See: https://www.cockroachlabs.com/blog/cockroachdb-ai-agents-managed-mcp-server/

## Prerequisites

- Cockroach Cloud cluster: `yare-roach`
- Database: `defaultdb`
- Existing Yare tables:
  - `yare_runs`
  - `yare_lead_artifacts`
  - `yare_current_states`
  - `yare_receipts`
- Prior Yare durable-memory run already persisted to CockroachDB
- An MCP-capable client such as Claude Code, Cursor, or VS Code

## Setup Steps

1. Open Cockroach Cloud.
2. Select the `yare-roach` cluster.
3. Click **Connect**.
4. Select **Model Context Protocol (MCP)**.
5. Copy the generated MCP client configuration snippet.
6. Paste the snippet into the local MCP client configuration for Claude Code, Cursor, or VS Code.
7. Keep the generated snippet local. Do not commit it.
8. Start or reload the MCP client.
9. Use the prompt in `docs/MCP_AGENT_PROMPT.md`.

## Expected Agent Behavior

The agent should use CockroachDB Managed MCP to inspect `defaultdb`, query the Yare tables, find the latest current-state record, and report:

- latest run/task
- current state hash
- what changed
- what is true
- what is unverified
- contradictions
- next clean action
- row counts for all Yare memory tables

## Result Recording

If the real MCP smoke test passes, add `docs/MCP_SMOKE_RESULT.md` with:

- date
- MCP client used
- credentials redacted
- latest run/task
- current state hash
- handoff summary
- row counts
- PASS status

If real MCP was not run, do not create `docs/MCP_SMOKE_RESULT.md`.
