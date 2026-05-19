---
id: skill.context-drift-audit
name: Context Drift Audit
description: Audit instruction drift, policy mismatch, and stale memory references.
version: 0.1.0
permissions:
  - filesystem:read
tags:
  - governance
  - drift
  - validation
---

# Context Drift Audit

Use this skill when the task asks for context quality checks, stale-instruction detection, or policy mismatch analysis.

## Procedure
1. Read `AGENTS.md`, active policies, and relevant memory markdown.
2. Flag contradictions, stale rules, and unresolved references.
3. Propose minimal corrective actions with explicit file paths.
