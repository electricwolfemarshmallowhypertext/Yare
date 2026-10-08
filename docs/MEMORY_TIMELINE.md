# Memory Timeline

Yare does not just remember state. It shows how agent truth changed over time.

The memory timeline reads CockroachDB-backed current-state records and prints a compact history of each compiled handoff.

## Timeline

```powershell
python -m cli.yare memory timeline
python -m cli.yare memory timeline --task "your task" --limit 25
```

The limit selects the newest states; they are displayed from earlier to later. The task filter keeps one task's history together.

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
python -m cli.yare memory diff --latest --task "your task"
```

The diff compares the newest two states of the selected task. Without a task filter, it uses the latest state's task. It shows:

- previous state hash
- latest state hash
- new truths
- removed truths
- still unresolved claims
- new unresolved claims
- resolved claims
- removed claims
- new contradictions
- cleared contradictions
- new approval items
- whether the next clean action changed

A claim is resolved only when the later state contains a supported fact or a recorded human approval for that claim. A claim that merely disappears is removed, not resolved.

## Requirements

Set `YARE_DATABASE_URL` before using timeline or diff commands:

```powershell
$env:YARE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
```

These commands do not add self-learning, optimizer behavior, or inferred intelligence. They compare stored Yare current-state records.
