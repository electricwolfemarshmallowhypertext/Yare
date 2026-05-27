# Skill Optimization (v0.3 Direction Stub)

Status: **NOT IMPLEMENTED**

## Purpose

AgentMD treats `skills/*/SKILL.md` files as external agent state.  
Future v0.3 should support controlled skill improvement with strict validation and auditability, without enabling uncontrolled self-evolving behavior.

## Core loop

```text
skill file
  -> run task/eval
  -> score output
  -> propose bounded add/delete/replace edit
  -> validate against held-out task
  -> accept only if score improves
  -> write skill receipt
```

## Design constraints

- Skill is external state, not model weight updates.
- Rollouts must be scored from explicit eval/task outcomes.
- Edit proposals are bounded to text operations only:
  - add
  - delete
  - replace
- Validation gate is mandatory before acceptance.
- Policy is accept-only-if-improved on held-out validation.
- Rejected edits are preserved in a rejected-edit buffer for traceability.
- Accepted edits generate a skill receipt with hashes, score delta, and validation summary.
- After a skill version is accepted, runtime execution should not require extra model calls for optimization during normal use.

## AgentMD alignment

This direction maps directly onto AgentMD primitives already in place:

- `skills/` for skill state
- validation/evals for scoring and gates
- deterministic hashes for state integrity
- receipts for audit trace

## Out of scope for v0.2

- No optimizer runtime logic
- No new CLI commands
- No autonomous self-editing loop
- No behavior changes to current v0.2 release candidate
