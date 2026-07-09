$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $repoRoot

if (-not $env:YARE_DATABASE_URL) {
    throw "YARE_DATABASE_URL must be set to run the real-use-case demo."
}

python -m cli.yare storage init

$args = @(
    "lead",
    "compile",
    "--task",
    "compile ai work lead state",
    "--artifact",
    "examples/lead-artifacts/run-codex.jsonl",
    "--artifact",
    "examples/lead-artifacts/run-claude.json",
    "--artifact",
    "examples/lead-artifacts/run-gemini.jsonl"
)

$compileOutput = & python -m cli.yare @args 2>&1
$exitCode = $LASTEXITCODE
$compileOutput | ForEach-Object { Write-Output $_ }

if ($exitCode -ne 0) {
    throw "yare lead compile failed with exit code $exitCode"
}

$deterministicHash = $null
foreach ($line in $compileOutput) {
    $text = [string]$line
    if ($text -match "deterministic_hash:\s*(\S+)") {
        $deterministicHash = $matches[1]
        break
    }
}

if (-not $deterministicHash) {
    throw "deterministic_hash not found in lead compile output"
}

$env:YARE_DEMO_CURRENT_STATE_HASH = $deterministicHash

$python = @'
import json
import os
import sys

import psycopg


def as_obj(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


def print_list(title, items):
    print(title)
    if items:
        for item in items:
            if isinstance(item, dict):
                text = item.get("text") or json.dumps(item, sort_keys=True)
            else:
                text = str(item)
            print(f"- {text}")
    else:
        print("- none")
    print()


database_url = os.environ["YARE_DATABASE_URL"]
state_hash = os.environ["YARE_DEMO_CURRENT_STATE_HASH"]

with psycopg.connect(database_url) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.task, r.current_state_hash, cs.state_json
            FROM yare_runs r
            JOIN yare_current_states cs
                ON cs.current_state_hash = r.current_state_hash
            WHERE r.current_state_hash = %s
            LIMIT 1
            """,
            (state_hash,),
        )
        row = cur.fetchone()

if row is None:
    print(f"No saved current state found for hash {state_hash}", file=sys.stderr)
    raise SystemExit(1)

task, current_state_hash, raw_state = row
state = as_obj(raw_state)

print("")
print("# Yare Current-State Handoff")
print("")
print(f"Task: {task}")
print(f"Current State Hash: {current_state_hash}")
print("")
print_list("## What Changed", state.get("what_changed", []))
print_list("## What Is True", state.get("what_is_true", []))
print_list("## What Is Unverified", state.get("what_is_unverified", []))
print_list("## Contradictions", state.get("what_contradicts_prior_state", []))
print("## Next Clean Action")
print(f"- {state.get('next_clean_action') or 'none'}")
'@

$python | python -c "import sys; exec(sys.stdin.read())"
