# Memory Timeline Smoke Result

Status: PASS

Date: 2026-07-09

## Scope

This smoke test verified Yare memory timeline and latest-state diff against the live CockroachDB cluster through `YARE_DATABASE_URL`.

No secrets are included.

## Database URL

Redacted DB URL:

```text
postgresql://REDACTED@yare-roach-28678.j77.aws-us-east-2.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full
```

## Commands

```powershell
python -m cli.yare memory timeline
```

Output:

```text
state_hash: 94776858ca61b6e768852437aed02471a23ee0e6cb0a13b7df5a4d9aed7899c9
created_at: 2026-07-09T12:32:02.693459+00:00
task: compile ai work lead state
run_id: demo-run-003
receipt_hash: 9ee44a117505047e6e854176a213f3d8fcce2331487367eeb92aee4944b2df30
changed_files_count: 4
verified_facts_count: 3
unresolved_claims_count: 1
contradictions_count: 1
human_approval_count: 3
next_clean_action: Resolve human-approval items before the next run.

state_hash: f1d815e9b18c9491c6d74c12bc737c67a2c1cd91386484dd49c6973c1dc6f399
created_at: 2026-07-09T12:49:54.127783+00:00
task: compile ai work lead state
run_id: demo-run-003
receipt_hash: 898587d20db3d21dfa9333bb021032e700894b56b47267530ccd777c072ff731
changed_files_count: 4
verified_facts_count: 3
unresolved_claims_count: 1
contradictions_count: 1
human_approval_count: 3
next_clean_action: Resolve human-approval items before the next run.

state_hash: 9a28c62809b16bcaffc49bfece25eca579b3020b24d1644438b0b6acadfa9859
created_at: 2026-07-09T13:14:39.193925+00:00
task: compile ai work lead state
run_id: demo-run-003
receipt_hash: 62373551749a4ba1c26a0ad7c2b7903f3d71653c5478db10816f6a4214419f4e
changed_files_count: 4
verified_facts_count: 3
unresolved_claims_count: 1
contradictions_count: 1
human_approval_count: 3
next_clean_action: Resolve human-approval items before the next run.

state_hash: 3e17416e734594685d1aa33a5502c0a4d0079595273e1e95b181e7b8a56d8a8a
created_at: 2026-07-09T22:44:14.099559+00:00
task: compile ai work lead state
run_id: demo-run-003
receipt_hash: 40510d9d51ae76672272f21bc8e8d663a3739f99b87310b9f2ab29f83ccd2d2f
changed_files_count: 4
verified_facts_count: 3
unresolved_claims_count: 1
contradictions_count: 1
human_approval_count: 3
next_clean_action: Resolve human-approval items before the next run.
```

```powershell
python -m cli.yare memory diff --latest
```

Output:

```text
previous_state_hash: 9a28c62809b16bcaffc49bfece25eca579b3020b24d1644438b0b6acadfa9859
latest_state_hash: 3e17416e734594685d1aa33a5502c0a4d0079595273e1e95b181e7b8a56d8a8a
new_truths:
- none
removed_truths:
- none
still_unresolved:
- All receipt tests passed in CI
new_unresolved_claims:
- none
resolved_claims:
- none
new_contradictions:
- none
cleared_contradictions:
- none
new_approval_items:
- none
next_clean_action_changed: no (Resolve human-approval items before the next run.)
```

## Result

Real CockroachDB memory timeline smoke passed.

The smoke read prior current-state records from CockroachDB and compared the latest state to the previous state.
