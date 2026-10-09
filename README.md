# Yare

**Shared work memory for AI agents.**

## What

Yare gives the next agent a clear handoff: what changed, what is verified, what remains unresolved, and what to do next.

It stores work state in CockroachDB with receipts that people and agents can inspect. A separate coding producer uses NVIDIA Nemotron through Nebius Token Factory to edit code and run tests inside OpenShell sandboxes.

- [Try the read-only A/B demo](https://yare-vert.vercel.app/demo)
- [Explore use cases](https://yare-vert.vercel.app/use-cases/)
- [Visit the project site](https://yare-vert.vercel.app/)

## Why

AI coding work gets scattered across tools, conversations, code changes, and test logs. When another agent takes over, a summary alone can hide unfinished work or a failed test.

Yare keeps actual test results, unverified claims, contradictions, approval items, and the next action together. The handoff survives a restart or a switch to another agent.

In the recorded A/B coding run, A passed four targeted tests but left two failures in the full suite. Fresh B loaded A's handoff from CockroachDB, fixed the remaining failures, and passed all six tests. OpenShell also allowed A and denied B access to the same sandboxed source snapshot while B worked in its separate copy.

The public demo reads the saved patches, test output, handoffs, and receipt hashes from those approved records. It does not start a coding run. [Read the recorded result](docs/NEMOTRON_BOUNDARY_RESULT.md).

## How

```text
Agent code changes and test results
-> Lead Artifacts
-> Yare validation and compile
-> CockroachDB work memory
-> next-agent handoff
```

Yare remains model agnostic: it compiles work artifacts regardless of which tool produced them. CockroachDB stores the current state and history; vector search finds prior handoff sections, and timeline diffs show what changed. Managed MCP lets agent clients query the same memory. Optional S3 archiving preserves proof files, and local exports work without cloud credentials.

Start locally:

```bash
git clone --branch nebius-upgrade https://github.com/electricwolfemarshmallowhypertext/Yare.git
cd Yare
python -m pip install -r requirements-cli.txt
python -m cli.yare doctor
```

The `nebius-upgrade` branch contains the coding producer and A/B handoff described here. `main` preserves the earlier release.

Compile the included artifacts into a local handoff:

```powershell
.\scripts\demo-lead-compile.ps1
```

To persist and retrieve memory, configure CockroachDB:

```powershell
$env:YARE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
python -m cli.yare storage init
.\scripts\demo-real-use-case.ps1
```

Inspect stored memory:

```powershell
python -m cli.yare memory search --query "what still needs human review?" --limit 3
python -m cli.yare memory timeline
python -m cli.yare memory diff --latest
```

Add `--task "your task"` to timeline or diff to inspect one task. Search combines vector distance with word and section matching, and removes duplicate results. Verified claims require linked test output or a recorded human review from a trusted source; Yare validates the record, not the identity of its author. Disputed claims stay outside confirmed facts. A claim disappearing from a later state is reported as removed, not resolved.

The coding producer requires Token Factory credentials and a configured OpenShell runtime. Its [integration documentation](docs/NEBIUS_PROVIDER_ROUTING.md) and [A/B run commands](docs/NEMOTRON_BOUNDARY_RESULT.md#live-handoff) describe the tested path. `yare run` prints launch instructions; the separate producer executes coding runs. Public paid execution is disabled.

Further recorded checks: [CockroachDB](docs/COCKROACH_SMOKE_RESULT.md), [vector indexing](docs/VECTOR_SMOKE_RESULT.md), [timeline](docs/MEMORY_TIMELINE_RESULT.md), [S3](docs/S3_SMOKE_RESULT.md), and MCP reads from [Claude Code](docs/MCP_SMOKE_RESULT.md), [Codex](docs/CODEX_MCP_SMOKE_RESULT.md), and [Cursor](docs/CURSOR_MCP_SMOKE_RESULT.md).

Yare is open source under the [MIT License](LICENSE).
