# CockroachDB Distributed Vector Indexing

Yare stores searchable agent memory vectors in CockroachDB.

After `yare lead compile` succeeds and `YARE_DATABASE_URL` is set, Yare persists the normal durable memory rows and also embeds the current-state handoff sections into `yare_memory_vectors`.

## What Is Embedded

- what changed
- what is true
- what is unverified
- contradictions
- human approval items
- open loops
- next clean action

Yare uses a deterministic local text-to-vector hashing function. It does not call OpenAI, Bedrock, or any external embedding service.

## CockroachDB Schema

The vector table uses CockroachDB's `VECTOR(32)` type and a real vector index:

```sql
CREATE TABLE IF NOT EXISTS yare_memory_vectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES yare_runs (run_id) ON DELETE CASCADE,
    current_state_hash TEXT NOT NULL,
    section_name TEXT NOT NULL,
    source_text TEXT NOT NULL,
    embedding VECTOR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (current_state_hash, section_name),
    VECTOR INDEX yare_memory_vectors_embedding_idx (embedding vector_cosine_ops)
);
```

CockroachDB vector indexes must be enabled on the cluster:

```sql
SET CLUSTER SETTING feature.vector_index.enabled = true;
```

Yare runs that setting during `storage init`. If the cluster does not support vector indexes or the user does not have permission to enable them, storage initialization fails instead of pretending vector search exists.

## Setup

```powershell
$env:YARE_DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
python -m cli.yare storage init
```

## Compile Memory

```powershell
python -m cli.yare lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
```

## Search Memory

```powershell
python -m cli.yare memory search --query "what still needs human review?" --limit 3
```

The command embeds the query locally, searches CockroachDB with the vector index, and prints:

- section name
- distance
- current state hash
- source text

## Query Shape

Yare searches with CockroachDB's cosine distance operator:

```sql
SELECT
    section_name,
    embedding <=> $1::VECTOR AS distance,
    current_state_hash,
    source_text
FROM yare_memory_vectors
ORDER BY embedding <=> $1::VECTOR
LIMIT $2;
```
