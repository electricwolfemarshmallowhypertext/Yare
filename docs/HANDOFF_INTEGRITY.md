# Handoff Integrity

Yare preserves code, test evidence, and receipts across separate agent runs.

## Spending Records

Local producer ledger updates are locked across processes. Each update reloads the current file before reserving or settling a call. New calls receive unique IDs; existing entries and approved limits are preserved. A missing usage result retains the reservation and blocks more calls.

## Stored Source

Each new current-state row stores its complete compiled packet, including its source artifacts. B reads that snapshot with the matching receipt and recalculates the state, receipt, and source-code hashes before using the code. Historical records can use the run's stored packet only when it matches the selected state hash. An unavailable or mismatched packet stops the handoff.

Run `python -m cli.yare storage init` to add the optional `packet_json` column to an existing database. Existing records and receipt hashes are preserved.

## Supported Claims

A claim labeled verified must reference a test record or a human review for that exact claim. Test records include the command, observed output, exit code, and expected exit code. Human reviews name the reviewer and approval. Claims without that evidence remain unverified; disputed claims are excluded from confirmed facts.

Example claim and linked controller-recorded test evidence:

```json
{
  "claims": [
    {"claim": "Targeted tests passed", "verification_status": "verified", "evidence_ref": "test_claim"}
  ],
  "evidence": {
    "test_claim": {
      "kind": "test",
      "claim": "Targeted tests passed",
      "command": ["python", "-m", "pytest", "tests/test_task.py"],
      "exit_code": 0,
      "expected_exit_code": 0,
      "stdout": "6 passed",
      "stderr": ""
    }
  }
}
```

The producer records the command result itself. Imported evidence must come from a trusted runner or reviewer; the compiler checks the supplied record and does not rerun an arbitrary command from an artifact.

## State Changes

The timeline selects the newest states and supports `--task`. Diff compares states from one task. Missing claims are shown as removed unless a supported fact or approved human decision establishes resolution.

## Regression Checks

```powershell
python -m pytest -q tests/producers tests/yare
python -m cli.yare doctor
.\scripts\demo-lead-compile.ps1
```

The regression suite covers concurrent reservations, altered handoff code and receipts, unsupported and disputed claims, removed claims, history ordering, and known search questions.
