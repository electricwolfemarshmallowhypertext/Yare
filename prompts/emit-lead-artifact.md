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
