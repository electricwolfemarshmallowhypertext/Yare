# Local Handoff Export

Use case:
Compile and inspect a handoff without configuring cloud services.

Who it is for:
Someone trying Yare locally or keeping an export beside the project.

What breaks today:
An agent summary may be scattered across source artifacts with no single local current-state file.

Why Yare fits:
`lead compile` writes local current-state JSON, Markdown, and a receipt even when the database and S3 environment variables are unset.

What Yare stores:
- compiled current-state JSON
- readable current-state Markdown
- receipt JSONL
- deterministic current-state hash

What Roach makes durable:
Nothing in this mode. CockroachDB is used only when `YARE_DATABASE_URL` is configured.

What the user sees:
Local `.sticky` output paths and hashes after the compile.

When they use it:
During local setup, offline review, or export from a database-backed run.

Why it matters:
The core compiler remains usable without cloud credentials.

Demo proof:
Run `scripts/demo-lead-compile.ps1` with `YARE_DATABASE_URL` and `YARE_S3_BUCKET` unset; the script prints the local output paths and deterministic hash.

One-line pitch:
Compile a local handoff and receipt without CockroachDB or S3 credentials.
