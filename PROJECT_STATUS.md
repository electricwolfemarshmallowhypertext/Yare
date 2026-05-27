# PROJECT_STATUS

## AgentMD Runtime v0.2

Status date: 2026-05-27

## Product framing

**AI Work Lead**: AgentMD compiles scattered AI/tool run artifacts into one deterministic, verified current-state packet with proof receipts.

Deployment model: **deployment-agnostic** (local, repo, CI, cloud, enterprise).

Current strongest claim:

- AgentMD compiles scattered AI/tool run artifacts into one deterministic current-state packet with proof receipts.

## What exists now

- `agentmd lead compile` ingests `.json` / `.jsonl` artifacts via repeatable `--artifact` flags.
- Lead Artifact input contract is versioned as **Lead Artifact v1** (`schema_version: "lead-artifact.v1"`).
- Schema validation is strict and requires `jsonschema` (pinned in `requirements-cli.txt`).
- Invalid artifacts fail with explicit schema errors.
- Runtime outputs are emitted to:
  - `.sticky/current-state.json`
  - `.sticky/current-state.md`
  - `.sticky/receipts/*.jsonl`
- Demo artifacts live in:
  - `examples/lead-artifacts/`
- Example outputs live in:
  - `examples/lead-output/`
- CI reproducibility workflow exists:
  - `AgentMD Lead Demo` (`.github/workflows/agentmd-lead-demo.yml`)

## Exact CLI demo command

```powershell
.\agentmd.cmd lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
```

## Output artifacts

Runtime outputs:

- `.sticky/current-state.json`
- `.sticky/current-state.md`
- `.sticky/receipts/*.jsonl`

Example/shareable outputs:

- `examples/lead-output/current-state.example.json`
- `examples/lead-output/current-state.example.md`

## Verification commands and results

Commands:

```powershell
python -m py_compile cli/agentmd.py
python -m pytest -q tests/agentmd/test_agentmd_cli.py
.\scripts\demo-lead-compile.ps1
```

Results:

- `py_compile`: PASS
- `pytest`: PASS (`16 passed`)
- demo script: PASS

## v0.2.0 Release Candidate

- Release line: AI Work Lead + Lead Artifact v1.
- Contract: strict schema validation with required `jsonschema` dependency.
- Proof: deterministic packet hash + receipt hash in runtime artifacts.
- CI proof path: `AgentMD Lead Demo` workflow.

## Intentionally out of scope

- SaaS platform features
- dashboard expansion/redesign
- tool-specific adapters
- auth/accounts
- cloud service layer
- agent swarm behavior
- persona marketplace/product surfacing
- unrelated runtime refactors

## Next recommended technical step (NOT IMPLEMENTED)

Run and publish one successful GitHub Actions proof (`AgentMD Lead Demo`) and only then tag `v0.2.0`.
