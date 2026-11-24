# Yare

**Shared work memory for AI agents.**

[Technical architecture](docs/ARCHITECTURE.md) | [Scientific continuity results](docs/SCIENTIFIC_HUMAN_REVIEW_RESULT.md)

## What

Yare lets one AI agent hand unfinished work to another without losing the evidence.

It saves code changes, actual test results, and remaining work in CockroachDB. The next agent can see what passed, what failed, and what still needs fixing instead of trusting the previous agent's claims.

- [View recorded coding handoffs](https://yare-vert.vercel.app/demo)
- [Explore use cases](https://yare-vert.vercel.app/use-cases/)
- [Visit the project site](https://yare-vert.vercel.app/)

## Why

AI coding work gets scattered across tools, conversations, code changes, and test logs. When another agent takes over, it needs more than a summary of what the previous agent says it did.

Yare keeps the work and its evidence together so the next agent can pick up unfinished work and people can review the results.

In one recorded coding task, the first agent passed four focused tests but left two failures in the full suite. A fresh agent loaded the saved handoff, finished the fix, and passed all six tests. This demonstrates that handoff on one task, not general autonomous coding performance.

The public demo shows recorded coding handoffs, including a four-agent chain and the earlier A/B task. It does not start a new agent run or display the scientific pilot. [Read the recorded A/B result](docs/NEMOTRON_BOUNDARY_RESULT.md).

In three scientific handoff sequences using public ZTF and Gaia observations, Yare preserved nine model-generated records and three deterministic human-review records. All twelve records and nine parent links were verified. Work-state continuity passed; the participating model's scientific reasoning failed. Its errors and unresolved questions were retained.

## How

```text
Agent code changes and test results
-> Lead Artifacts
-> Yare validation and compile
-> CockroachDB work memory
-> next-agent handoff
```

An agent produces a work record containing its changes, test output, claims, and unfinished work. Yare checks that record, builds a handoff, and saves it with receipts in CockroachDB. The next agent loads the handoff and checks the saved code and record hashes before continuing.

Yare stores the handoff; it is not the coding model. The separate coding producer uses NVIDIA Nemotron through Nebius Token Factory inside OpenShell sandboxes. Local exports are available without cloud credentials. S3 archiving is optional.

Start locally:

```bash
git clone --branch scientific-work-continuity https://github.com/electricwolfemarshmallowhypertext/Yare.git
cd Yare
python -m pip install -r requirements-cli.txt
python -m cli.yare doctor
```

The `scientific-work-continuity` branch contains the coding producer and scientific continuity work described here. `nebius-upgrade` preserves the coding upgrade; `main` preserves the earlier release.

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

Add `--task "your task"` to timeline or diff to inspect one task. The [technical architecture](docs/ARCHITECTURE.md) explains search, evidence checks, history, and their limits.

The coding producer requires Token Factory credentials and a configured OpenShell runtime. Its [integration documentation](docs/NEBIUS_PROVIDER_ROUTING.md) and [A/B run commands](docs/NEMOTRON_BOUNDARY_RESULT.md#live-handoff) describe the tested path. `yare run` prints launch instructions; the separate producer executes coding runs. Public paid execution is disabled.

Further recorded checks: [CockroachDB](docs/COCKROACH_SMOKE_RESULT.md), [vector indexing](docs/VECTOR_SMOKE_RESULT.md), [timeline](docs/MEMORY_TIMELINE_RESULT.md), [S3](docs/S3_SMOKE_RESULT.md), and MCP reads from [Claude Code](docs/MCP_SMOKE_RESULT.md), [Codex](docs/CODEX_MCP_SMOKE_RESULT.md), and [Cursor](docs/CURSOR_MCP_SMOKE_RESULT.md).

Yare is open source under the [MIT License](LICENSE).
