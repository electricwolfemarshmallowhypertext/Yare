# Yare Project Instructions

## Project Rules
- Keep Sticky persona architecture internal as behavioral architecture packs.
- Public surface area is verified work-state memory: instructions, skills, memory, policies, evals, receipts.
- Hackathon architecture: CockroachDB is the primary system of record for verified working memory.
- Local `.yare` and `.sticky` files may remain as optional fallback/export modes.
- Do not build a notes product workflow or persona marketplace workflow in Yare v1.

## Setup Commands
- `python -m pip install -r requirements-cli.txt`
- `python -m cli.yare doctor`
- Set `YARE_DATABASE_URL` only when testing CockroachDB-backed durable memory.
- Set `YARE_S3_BUCKET` only when testing Amazon S3 proof artifact archive.
- `python -m cli.yare storage init`

## Test Commands
- `python -m pytest -q tests/yare/test_yare_cli.py`

## Architecture Constraints
- `AGENTS.md` is the root instruction layer.
- `skills/*/SKILL.md` is procedural capability metadata and instructions.
- `memory/*.md` is markdown-first project-owned memory.
- `policies/*.yaml` defines governance rules.
- `evals/*.jsonl` stores eval fixtures and traces.
- `receipts/*.jsonl` is immutable execution receipt output.

## Agent Boundaries
- Yare must validate and explain context selection before execution.
- Receipt output must include selected files, hashes, validation state, and reproducibility metadata.
- Persona runtime internals remain reusable but hidden from Yare public framing.
