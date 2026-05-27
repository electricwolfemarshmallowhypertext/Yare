# AgentMD: compiling scattered AI runs into one verified current-state packet

## 1. Problem

AI-assisted work creates scattered artifacts across Codex, Claude, Gemini, chats, CI, and scripts.  
The failure mode is losing the actual current state of work.

## 2. Claim

AgentMD compiles scattered AI/tool run artifacts into one deterministic current-state packet.

## 3. Demo input

Lead Artifact demo inputs:

- `examples/lead-artifacts/run-codex.jsonl`
- `examples/lead-artifacts/run-claude.json`
- `examples/lead-artifacts/run-gemini.jsonl`

Reference outputs:

- `examples/lead-output/current-state.example.md`
- `examples/lead-output/current-state.example.json`

## 4. Before -> After

Before:

- scattered Codex/Claude/Gemini run artifacts

After:

- one compiled current-state packet
- one receipt trail

## 5. Command

```powershell
.\scripts\demo-lead-compile.ps1
```

## 6. Output

The compile writes:

- `.sticky/current-state.json`
- `.sticky/current-state.md`
- `.sticky/receipts/*.jsonl`

## 7. Packet excerpt (from example output)

Excerpt source: `examples/lead-output/current-state.example.md`

```text
## What Changed
## What Is True
## What Is Unverified
## What Contradicts Prior State
## What Needs Human Approval
## Open Loops
## Next Clean Action
```

## 8. What the packet contains

- what changed
- what is true
- what is unverified
- contradictions
- human approval items
- open loops
- next clean action

## 9. Schema proof

Lead Artifact v1 validates input artifacts.  
Invalid artifacts fail clearly.

Schema:

- `schemas/lead-artifact.schema.json`

## 10. CI and release proof

- CI: green
- AgentMD Lead Demo: green
- GitHub Actions: `https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/actions`
- Release: `v0.3.0-alpha.2`
- Release URL: `https://github.com/electricwolfemarshmallowhypertext/agentmd-runtime/releases/tag/v0.3.0-alpha.2`

Current verified facts:

- tests: `20 passed`
- workflows: CI green, AgentMD Lead Demo green
- latest release: `v0.3.0-alpha.2`
- latest release commit: `6efc66d`

## 11. Skill gate proof

Accepted skill edit writes:

- `.sticky/skill-receipts/*.jsonl`

Rejected skill edit writes:

- `.sticky/rejected-skill-edits/*.jsonl`

Schema:

- `schemas/skill-edit.schema.json`

## 12. What this proves

- artifacts can be normalized
- schema validation works
- deterministic packet generation works
- proof receipts are written
- skill edits are gated by validation score

## 13. What this does not prove yet

- production SaaS readiness
- full adapter automation
- multi-user/team workflow
- autonomous optimizer loop
- security hardening for hostile inputs

## 14. Boundaries

- Alpha release.
- Evaluation/research/internal testing use.
- Not production SaaS.
- Not an agent swarm.
- Not a hosted platform.
- Optimizer loop is not implemented yet.
