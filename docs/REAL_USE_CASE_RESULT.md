# Real Use Case Result

Date: 2026-07-09

## Scope

This run verified the coding handoff demo against CockroachDB.

No secrets or connection strings are recorded here.

## Result

Real-use-case demo passed locally against CockroachDB.

Yare persisted state to CockroachDB, read it back, and printed the handoff for a follow-on coding agent.

## Run Output

```text
storage: initialized
tables: yare_runs, yare_lead_artifacts, yare_current_states, yare_receipts
deterministic_hash: f1d815e9b18c9491c6d74c12bc737c67a2c1cd91386484dd49c6973c1dc6f399
receipt_hash: 898587d20db3d21dfa9333bb021032e700894b56b47267530ccd777c072ff731
```

## Handoff Printed

- what changed
- what is true
- what is unverified
- contradictions
- next clean action
