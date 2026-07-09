# MCP Agent Prompt

Use CockroachDB MCP to inspect the Yare memory tables in defaultdb.

Find the latest current-state record.

Report:

- latest run/task
- current state hash
- what changed
- what is true
- what is unverified
- contradictions
- next clean action

Also report row counts for:

- yare_runs
- yare_lead_artifacts
- yare_current_states
- yare_receipts
