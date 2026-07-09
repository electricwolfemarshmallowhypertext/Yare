# Codex MCP Smoke Result

Status: PASS

Client: Codex

MCP server: `cockroachdb-cloud`

Database: `defaultdb`

Row counts:

- `yare_runs`: 1
- `yare_lead_artifacts`: 3
- `yare_current_states`: 3
- `yare_receipts`: 4

Latest current-state hash:

`9a28c62809b16bcaffc49bfece25eca579b3020b24d1644438b0b6acadfa9859`

Latest run:

- `run_id`: `demo-run-003`
- `task`: `compile ai work lead state`

Handoff confirmed:

- changed files
- true claims
- unverified claims
- contradiction
- human approval items
- next clean action

Codex queried CockroachDB through MCP, not Yare's Python database code.

No secrets were included.
