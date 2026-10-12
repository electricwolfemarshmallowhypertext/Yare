# Emit Lead Artifact JSON

Use this prompt in any AI tool (Codex, Claude, Gemini, ChatGPT, Cursor) to emit a valid Yare Lead Artifact without a custom adapter.

## Copy/Paste Prompt

Output exactly one JSON object that matches Yare Lead Artifact schema.

Rules:
- Output JSON only. No markdown. No comments.
- Include all required fields exactly:
  - `schema_version`
  - `run_id`
  - `tool`
  - `task`
  - `timestamp`
  - `claims`
  - `decisions`
  - `files_touched`
  - `open_loops`
  - `contradictions`
  - `human_approval_items`
  - `verification_status`
- Set `schema_version` to exactly `lead-artifact.v1`.
- Use empty arrays (`[]`) when nothing applies.
- Do not invent verification. If uncertain, mark as unverified.
- A `verified` label alone is insufficient. For a supported claim, include inline `evidence` or an `evidence_ref` pointing to a named record in the artifact's top-level `evidence` object.
- Test evidence must have `kind: "test"`, the exact matching `claim`, actual argv in `command`, actual integer `exit_code`, integer `expected_exit_code`, and recorded `stdout` or `stderr`. An expected/actual exit match without any output is not accepted as supported. Never fabricate command output.
- Human review evidence must have `kind: "human_review"`, the exact matching `claim`, actual `reviewer`, and `decision: "approved"`. Only record an approval that actually happened.
- If evidence is missing or the test failed, leave the claim unverified; retain the actual failed result as evidence, not as a passing fact.
- Yare checks supplied evidence from trusted sources; these records do not authenticate their author's identity.
- Use `verification_status` as `unverified` when overall status is unknown.
- `timestamp` must be ISO-8601 UTC format, for example `2026-05-27T00:00:00Z`.

Output shape:

```json
{
  "schema_version": "lead-artifact.v1",
  "run_id": "string",
  "tool": "string",
  "task": "string",
  "timestamp": "2026-05-27T00:00:00Z",
  "claims": [],
  "decisions": [],
  "files_touched": [],
  "open_loops": [],
  "contradictions": [],
  "human_approval_items": [],
  "verification_status": "unverified"
}
```

For a real captured test, a claim can use this shape (replace values with observed results):

```json
{
  "claim": "The targeted test passed",
  "verification_status": "verified",
  "evidence": {
    "kind": "test",
    "claim": "The targeted test passed",
    "command": ["python", "-m", "unittest", "test_example"],
    "exit_code": 0,
    "expected_exit_code": 0,
    "stdout": "",
    "stderr": "Actual captured test output goes here; do not copy this placeholder"
  }
}
```
