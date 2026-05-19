# AgentMD Project Instructions

## Project Rules
- Keep Sticky persona architecture internal as behavioral architecture packs.
- Public surface area is context governance: instructions, skills, memory, policies, evals, receipts.
- Do not build a notes product workflow or persona marketplace workflow in AgentMD v1.

## Setup Commands
- `python -m pip install -r requirements-cli.txt`
- `python -m cli.agentmd doctor`

## Test Commands
- `python -m pytest -q tests/agentmd/test_agentmd_cli.py`

## Architecture Constraints
- `AGENTS.md` is the root instruction layer.
- `skills/*/SKILL.md` is procedural capability metadata and instructions.
- `memory/*.md` is markdown-first project-owned memory.
- `policies/*.yaml` defines governance rules.
- `evals/*.jsonl` stores eval fixtures and traces.
- `receipts/*.jsonl` is immutable execution receipt output.

## Agent Boundaries
- AgentMD must validate and explain context selection before execution.
- Receipt output must include selected files, hashes, validation state, and reproducibility metadata.
- Persona runtime internals remain reusable but hidden from AgentMD public framing.
