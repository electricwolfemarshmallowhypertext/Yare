# Memory System Development Guide

## Supported Yare Upgrade

Use `nebius-upgrade` for the supported coding-handoff release; `main` preserves the earlier release and is not merged automatically. Production follows `nebius-upgrade`.

Install CLI dependencies with `python -m pip install -r requirements-cli.txt`, then run `python -m cli.yare doctor`. CI runs this before installing pytest, so a separately installed YAML dependency cannot hide an incomplete quickstart.

Supported automated checks are `python -m pytest -q tests/` and the Node tests in `tests/site/*.cjs` and `site/tests/*.test.js`. CI runs them on both upgrade branches and pull requests. Cloud checks require explicitly configured access and are separate from offline fixtures.

The older `apps/api/tests` suite belongs to the legacy API stack, requires its own `apps/api/requirements.txt` dependencies, and is not included in the supported Yare CLI/producer/site CI job. The older setup instructions below apply to that stack, not the CLI quickstart.

Created: 2025-11-02 20:06:54
Author: electricwolfemarshmallowhypertext

## Development Setup

### Prerequisites

```bash
# Required system packages
sudo apt-get update && sudo apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    build-essential \
    redis-server \
    sqlite3 \
    zstd

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Real CockroachDB Smoke Test

Use a real CockroachDB connection to prove durable Yare memory persistence. Do not commit credentials.

Local single-node example:

```powershell
docker run --rm -d --name yare-cockroach-smoke -p 26257:26257 -p 8080:8080 cockroachdb/cockroach:v23.1.28 start-single-node --insecure --listen-addr=0.0.0.0:26257 --http-addr=0.0.0.0:8080
$env:YARE_DATABASE_URL = "postgresql://root@localhost:26257/defaultdb?sslmode=disable"
python -m cli.yare storage init
python -m cli.yare lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
docker exec yare-cockroach-smoke ./cockroach sql --insecure --execute "SELECT 'yare_runs' AS table_name, count(*) FROM yare_runs UNION ALL SELECT 'yare_lead_artifacts', count(*) FROM yare_lead_artifacts UNION ALL SELECT 'yare_current_states', count(*) FROM yare_current_states UNION ALL SELECT 'yare_receipts', count(*) FROM yare_receipts;"
docker stop yare-cockroach-smoke
```

CockroachCloud example:

```powershell
$env:YARE_DATABASE_URL = "postgresql://<user>:<redacted>@<cluster-host>:26257/defaultdb?sslmode=verify-full"
python -m cli.yare storage init
python -m cli.yare lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
```
