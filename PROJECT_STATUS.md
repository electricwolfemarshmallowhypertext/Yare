# PROJECT_STATUS

## Yare v0.2

Status date: 2026-05-27

## Product framing

**AI Work Lead**: Yare turns scattered AI work into verified working memory with deterministic current-state packets and proof receipts.

Deployment model: **deployment-agnostic** (local, repo, CI, cloud, enterprise).

Current strongest claim:

- Yare is verified work-state memory for agents, not chat memory or generic project notes.
- Yare compiles scattered AI/tool run artifacts into one deterministic current-state packet with proof receipts.
- Hackathon version target: CockroachDB is the primary durable system of record for verified working memory.
- Local `.yare` and `.sticky` outputs remain optional fallback/export modes.
- S3 is the receipt/artifact archive target.

## What exists now

- `yare lead compile` ingests `.json` / `.jsonl` artifacts via repeatable `--artifact` flags.
- `python -m cli.yare storage init` creates CockroachDB-compatible durable memory tables.
- When `YARE_DATABASE_URL` is set, `yare lead compile` persists verified working memory to CockroachDB after local compile output succeeds.
- When `YARE_S3_BUCKET` is set, `yare lead compile` archives proof artifacts to Amazon S3 after local compile output succeeds.
- Lead Artifact input contract is versioned as **Lead Artifact v1** (`schema_version: "lead-artifact.v1"`).
- Schema validation is strict and requires `jsonschema` (pinned in `requirements-cli.txt`).
- Invalid artifacts fail with explicit schema errors.
- Runtime outputs are emitted to:
  - `.sticky/current-state.json`
  - `.sticky/current-state.md`
  - `.sticky/receipts/*.jsonl`
- Hackathon target architecture:
  - CockroachDB stores verified working memory as the source of truth.
  - Local `.yare` and `.sticky` files remain fallback/export artifacts.
  - S3 archives receipts and artifacts.
- Demo artifacts live in:
  - `examples/lead-artifacts/`
- Example outputs live in:
  - `examples/lead-output/`
- CI reproducibility workflow exists:
  - `Yare Lead Demo` (`.github/workflows/yare-lead-demo.yml`)

## Exact CLI demo command

```powershell
.\yare.cmd lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
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
python -m py_compile cli/yare.py
python -m pytest -q tests/yare/test_yare_cli.py
python -m cli.yare doctor
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
- CI proof path: `Yare Lead Demo` workflow.

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

Run and publish one successful GitHub Actions proof (`Yare Lead Demo`) and only then tag `v0.2.0`.
