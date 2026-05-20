# AgentMD Runtime

**AgentMD is a context governance runtime for AI agents.**

It makes `AGENTS.md`, skills, memory, policies, evals, and execution receipts executable, versioned, and auditable.

AgentMD is not a notes app, persona marketplace, or prompt-pack wrapper. It is a local-first runtime for governing the context agents use before, during, and after execution.

## Problem

Production AI teams increasingly rely on assembled context stacks: repo instructions, skill files, memory notes, policies, evals, local docs, CLI agents, and model-specific workflows.

The failure point is not only retrieval. It is context governance:

- stale instructions
- conflicting skills
- unmanaged memory
- invisible context selection
- unaudited execution
- no reproducible trace of why an agent acted

AgentMD turns agent context into a verifiable runtime surface.

## Core idea

```text
task
  â†’ validate workspace
  â†’ resolve relevant context
  â†’ hash selected context bundle
  â†’ run or prepare agent execution
  â†’ write receipt
  â†’ show explainable results
```

## What AgentMD governs

```text
AGENTS.md                  repo-level operating rules
agentmd.yaml               AgentMD workspace config
skills/*/SKILL.md          procedural agent capabilities
memory/*.md                durable project/context memory
policies/*.yaml            governance and permission rules
evals/*.jsonl              context-selection/evaluation fixtures
receipts/*.jsonl           auditable execution receipts
.agentmd/resolved-context.json
                            latest explainable context bundle
```

## Current v0.1 capabilities

### CLI

AgentMD currently provides four core commands:

```powershell
.\agentmd.cmd doctor
.\agentmd.cmd resolve --task "review this repo for context drift"
.\agentmd.cmd receipt
.\agentmd.cmd run --adapter codex --task "review this repo for context drift"
```

### `doctor`

Validates the workspace:

- required files and directories
- `AGENTS.md`
- `agentmd.yaml`
- skill metadata
- duplicate skill IDs
- forbidden skill permissions
- YAML policies
- JSONL evals
- markdown-only memory files
- broken local references
- context size limits

JSON output is supported:

```powershell
.\agentmd.cmd doctor --json
```

### `resolve`

Selects context for a task and explains why each file was selected or excluded.

```powershell
.\agentmd.cmd resolve --task "review this repo for context drift"
```

Custom output path:

```powershell
.\agentmd.cmd resolve --task "review this repo for context drift" --output .agentmd\resolved-custom.json
```

JSON output:

```powershell
.\agentmd.cmd resolve --task "review this repo for context drift" --json
```

Resolved context includes:

- task
- selected context files
- excluded context files
- selection reasons
- exclusion reasons
- file hashes
- estimated token/size data
- deterministic `context_bundle_hash`

### `receipt`

Writes an auditable execution receipt.

```powershell
.\agentmd.cmd receipt
```

Receipts include:

- task
- adapter
- selected context files
- file hashes
- context bundle hash
- resolved context source file
- git commit
- dirty status
- changed files
- untracked files
- validation status
- deterministic receipt hash

### `run`

Prepares an adapter run for supported agent CLIs.

```powershell
.\agentmd.cmd run --adapter codex --task "review this repo for context drift"
.\agentmd.cmd run --adapter claude --task "review this repo for context drift"
.\agentmd.cmd run --adapter gemini --task "review this repo for context drift"
```

v0.1 does not deeply integrate with each external agent runtime yet. It resolves context and records receipts around the intended execution path.

## Explainable Results UI

AgentMD includes a minimal explainable results dashboard.

Endpoint:

```text
/agentmd/results
```

Static UI:

```text
/dashboard/agentmd-results.html
```

The UI shows:

- task
- selected context files
- why each file was selected
- excluded files and reasons
- validation status
- context bundle hash
- latest receipt hash
- git commit
- dirty status
- changed/untracked files
- file/change distribution
- receipt integrity signals

The page uses a clean enterprise layout and Chart.js visualizations. It does not add auth, database state, or platform behavior.

## Quickstart

From the repo root:

```powershell
cd E:\sticky-local-agentmd
```

Run validation:

```powershell
.\agentmd.cmd doctor
```

Resolve context:

```powershell
.\agentmd.cmd resolve --task "review this repo for context drift"
```

Write a receipt:

```powershell
.\agentmd.cmd receipt
```

Run tests:

```powershell
python -m pytest -q tests/agentmd/test_agentmd_cli.py
```

Expected current result:

```text
8 passed
```

## Server verification

Start the FastAPI server:

```powershell
python -m uvicorn apps.api.src.memory.server:app --host 127.0.0.1 --port 8011
```

Check the AgentMD results endpoint:

```powershell
Invoke-WebRequest http://127.0.0.1:8011/agentmd/results
```

Check the dashboard page:

```powershell
Invoke-WebRequest http://127.0.0.1:8011/dashboard/agentmd-results.html
```

## Design principles

AgentMD follows a file-native agent context model:

1. **Context should be inspectable.**
   Agents should not operate from invisible prompt soup.

2. **Context should be versioned.**
   Repo rules, memory, policies, and skills should live as files.

3. **Context should be selected deliberately.**
   The runtime should explain why context was included or excluded.

4. **Context should be auditable.**
   Every execution should produce a receipt.

5. **Context should be portable.**
   AgentMD should work across Codex, Claude, Gemini, local agents, and future adapters.

## What v0.1 intentionally does not include

AgentMD v0.1 does not include:

- hosted SaaS
- auth
- team accounts
- database-backed workspace state
- persona marketplace
- model marketplace
- full adapter automation
- enterprise policy UI
- billing
- remote sync

Those are later layers. v0.1 proves the core runtime:

```text
validate â†’ resolve â†’ hash â†’ receipt â†’ explain
```

## License

AgentMD Runtime is source-available under **Business Source License 1.1 (BUSL-1.1)**.

Commercial production use, hosted service use, resale, embedding into commercial
products, or offering substantially similar functionality as a service requires a
commercial license from the Licensor.

See `LICENSE`, `LICENSE.md`, and `NOTICE` for details.
## Repository status
Current verified state:

```text
doctor: PASS
AgentMD tests: 8 passed
remote: electricwolfemarshmallowhypertext/agentmd-runtime
branch: main
```

Recent milestone commits:

```text
91210b9 add AgentMD explainable results UI
973f411 fix AgentMD receipt source tracking
c4d3aa4 harden AgentMD context governance CLI
371a14f initial AgentMD Sticky runtime
```

## Positioning

**AgentMD makes agent context executable.**

It gives AI teams a local-first way to validate, resolve, version, hash, and audit the context their agents depend on.

The result is a reproducible context trace:

```text
What did the agent use?
Why did it use it?
What policy applied?
What changed?
What receipt proves it?
```

