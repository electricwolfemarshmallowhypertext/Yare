# Yare

**Shared work memory for AI agents.**

Yare shows the next agent what happened, what changed, what is still unresolved, and what needs human review.

## Try It

- Live demo: https://yare-vert.vercel.app/demo
- Project site: https://yare-vert.vercel.app/
- Use cases: https://yare-vert.vercel.app/use-cases.html

## Why It Exists

AI coding work gets scattered fast.

Codex changes files. Claude explains something else. Cursor picks it up later. CI adds another signal. Then a human has to reconstruct the truth from chats, logs, diffs, and guesses.

Yare gives the work one shared memory.

## What It Does

Yare turns agent work into a clear handoff:

- what changed
- what is true
- what is unresolved
- what contradicts
- what needs review
- what changed since the last run
- what to do next

## How It Works

```text
AI/tool runs
→ Lead Artifacts
→ Yare compile
→ CockroachDB memory
→ vector search + timeline diff
→ S3 archive
→ next-agent handoff
```

CockroachDB stores the memory.
S3 stores the artifacts.
MCP lets agent clients inspect the same state.

## What Makes It Useful

Yare does not just save notes.

It keeps a durable work state, tracks how that state changes over time, supports semantic search across prior handoffs, and keeps receipts humans can review.

## Verified With

- CockroachDB durable memory
- CockroachDB Distributed Vector Indexing
- CockroachDB Managed MCP
- Amazon S3 archive
- Claude Code
- Codex
- Cursor
- Vercel live demo

Details are in `docs/`.

## Quickstart

```bash
git clone https://github.com/electricwolfemarshmallowhypertext/Yare.git
cd Yare
python -m pip install -r requirements-cli.txt
python -m cli.yare doctor
```

Run the demo compile:

```powershell
.\scripts\demo-lead-compile.ps1
```

Run the handoff demo:

```powershell
.\scripts\demo-real-use-case.ps1
```

## CockroachDB

Set `YARE_DATABASE_URL` to store memory in CockroachDB:

```powershell
$env:YARE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
python -m cli.yare storage init
```

## Core Commands

```powershell
python -m cli.yare storage init
python -m cli.yare lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
python -m cli.yare memory search --query "what still needs human review?" --limit 3
python -m cli.yare memory timeline
python -m cli.yare memory diff --latest
```

## Use Cases

See `docs/use-cases/`.

Start with:

- AI coding teams
- engineering audit
- compliance teams
- vibe coders
- content and research operators
- devtool founders and AI agencies

## License

MIT
