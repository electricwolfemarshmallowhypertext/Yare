# Yare

**Durable work memory for AI agents.**

Yare gives coding agents a clean handoff: what changed, what is true, what is unresolved, what needs human review, and what to do next.

It stores that memory in CockroachDB, archives proof artifacts to S3, and lets agent clients inspect the same state through CockroachDB Managed MCP.

## Why Yare Exists

AI coding work gets messy fast.

One agent changes files.
Another claims tests passed.
CI says something else.
A human comes back later and has to reconstruct the truth from chats, logs, diffs, and guesses.

Yare keeps the work state readable.

## What Yare Gives You

- changed files
- verified facts
- unverified claims
- contradictions
- human approval items
- open loops
- proof receipts
- next clean action

## How It Works

```text
AI/tool runs
-> Lead Artifacts
-> Yare compile
-> CockroachDB memory
-> S3 proof archive
-> agent handoff
```

CockroachDB is the durable memory store.
S3 stores proof artifacts.
Local `.yare` and `.sticky` files remain export/fallback files.

## Real Demo

```powershell
.\scripts\demo-real-use-case.ps1
```

The demo compiles prior AI runs, stores the state in CockroachDB, reads it back, and prints a handoff another agent can use.

## Proof

- CockroachDB memory smoke: `docs/COCKROACH_SMOKE_RESULT.md`
- Real handoff demo: `docs/REAL_USE_CASE_RESULT.md`
- S3 archive smoke: `docs/S3_SMOKE_RESULT.md`
- Claude Code MCP proof: `docs/MCP_SMOKE_RESULT.md`
- Codex MCP proof: `docs/CODEX_MCP_SMOKE_RESULT.md`
- Cursor MCP proof: `docs/CURSOR_MCP_SMOKE_RESULT.md`

## Use Cases

See `docs/use-cases/`.

Start here:

- AI coding teams
- Engineering audit
- Compliance teams
- Vibe coders
- Content and research operators
- Devtool founders and AI agencies

## Quickstart

```bash
git clone https://github.com/electricwolfemarshmallowhypertext/Yare.git
cd Yare
```

```powershell
python -m pip install -r requirements-cli.txt
python -m cli.yare doctor
.\scripts\demo-lead-compile.ps1
```

## CockroachDB

```powershell
$env:YARE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
python -m cli.yare storage init
```

## S3 Archive

```powershell
$env:YARE_S3_BUCKET = "your-bucket"
$env:YARE_S3_PREFIX = "yare/"
```

## Core Command

```powershell
.\yare.cmd lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
```

## License

MIT
