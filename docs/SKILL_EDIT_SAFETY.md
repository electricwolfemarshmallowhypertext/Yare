# Skill Edit Safety

`skill apply-edit` validates a bounded proposal targeting a file inside `skills/`.
Absolute paths, parent traversal and symlink escapes are rejected.

A proposal's `baseline_score` and `validation_score` are not acceptance evidence.
Without an operator-configured evaluator, proposals are recorded as rejected with
`skill_edit_independent_evaluation_required` and the skill remains unchanged.

## Configure Evaluation

The operator, not the proposing agent, controls the ignored local configuration
`.yare/skill-evaluator.json` and its approved evaluator program:

```json
{
  "program": "scripts/approved-skill-evaluator.py",
  "program_sha256": "SHA256_OF_THE_APPROVED_PROGRAM",
  "timeout_seconds": 60
}
```

The program must be a Python file inside `scripts/`. Yare runs it separately for
the original skill and the proposed skill, passing the skill-file path and
`validation_task` as positional arguments. Its standard output must be JSON:

```json
{
  "skill_sha256": "SHA256_OF_THE_SKILL_EVALUATED",
  "cases": [{"id": "case-1", "passed": true}]
}
```

The evaluator must actually perform the checks represented by those cases.
Author-supplied result files are not an evaluator. Protect the local configuration
and approved program from the proposing agent; this is a trust requirement, not
a sandbox supplied by Yare. No evaluator is installed or enabled automatically.

Yare checks the program hash before and after execution, rejects missing,
duplicate or mismatched case IDs, checks the evaluated skill hashes, and computes
each score as passed cases divided by total cases. Both evaluations must use the
same cases. Timeout, nonzero exit, oversized output or invalid results reject the
edit rather than falling back to proposal scores.

An accepted proposal must include `old_hash` matching the original skill and have
a strictly higher measured score. Before replacement, Yare rechecks the source
hash and confined path, checks the temporary candidate hash, then replaces the
skill from a temporary file in the same directory. The receipt includes measured
case outcomes and evaluator/source hashes. This does not prevent an authorized
operator from configuring a dishonest evaluator.

Focused offline verification passed all 11 cases: measured acceptance, rejection
of forged improvement scores, missing evaluator/original hash, protected paths,
changed evaluator and source drift before/after evaluation. The evaluator used
temporary fixture workspaces only. These checks establish gate behavior, not
real-world skill quality. No evaluator was installed in the project and no model
or database service was called.
