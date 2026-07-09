# Memory Timeline

Yare does not just remember state. It shows how agent truth changed over time.

The memory timeline reads CockroachDB-backed current-state records and prints a compact history of each compiled handoff.

## Timeline

```powershell
python -m cli.yare memory timeline
```

Each timeline entry shows:

- state hash
- created time
- task
- run ID
- receipt hash
- changed files count
- verified facts count
- unresolved claims count
- contradictions count
- human approval count
- next clean action

## Diff Latest State

```powershell
python -m cli.yare memory diff --latest
```

The diff compares the latest current state to the previous current state and shows:

- previous state hash
- latest state hash
- new truths
- removed truths
- still unresolved claims
- new unresolved claims
- resolved claims
- new contradictions
- cleared contradictions
- new approval items
- whether the next clean action changed

## Requirements

Set `YARE_DATABASE_URL` before using timeline or diff commands:

```powershell
$env:YARE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
```

These commands do not add self-learning, optimizer behavior, or inferred intelligence. They compare stored Yare current-state records.
