# CockroachDB Managed MCP Smoke Result

Status: PASS

Client: Claude Code

MCP server: `cockroachdb-cloud`

Cluster: `yare-roach`

Database: `defaultdb`

Row counts:

- `yare_runs`: 1
- `yare_lead_artifacts`: 3
- `yare_current_states`: 3
- `yare_receipts`: 4

Latest run:

- `run_id`: `demo-run-003`
- `task`: `compile ai work lead state`

Latest current-state hash:

`9a28c62809b16bcaffc49bfece25eca579b3020b24d1644438b0b6acadfa9859`

Latest receipt hash:

`62373551749a4ba1c26a0ad7c2b7903f3d71653c5478db10816f6a4214419f4e`

Handoff fields confirmed:

- what changed
- what is true
- what is unverified
- contradictions
- human approval items
- next clean action

MCP queried CockroachDB directly, not Yare's Python database code.

No secrets were included.
