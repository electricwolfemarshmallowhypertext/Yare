# Archive Proof Artifacts

Use case:
Keep compiled state exports and receipts outside the working directory.

Who it is for:
Teams that need to retain the files behind a Yare handoff.

What breaks today:
Local proof files can disappear when a workspace or sandbox is replaced.

Why Yare fits:
When an S3 bucket is configured, `lead compile` uploads the current-state JSON, Markdown, and receipt.

What Yare stores:
- current-state JSON
- current-state Markdown
- receipt JSONL
- deterministic object keys

What Roach makes durable:
CockroachDB remains the primary store for working memory; S3 is an archive for proof files.

What the user sees:
S3 object URIs printed after a successful compile.

When they use it:
After compiling a handoff that needs an external proof archive.

Why it matters:
The files supporting a handoff are not confined to one local workspace.

Demo proof:
The Amazon S3 smoke test uploaded and confirmed all three objects. See `docs/S3_SMOKE_RESULT.md`.

One-line pitch:
Archive current-state exports and receipts to Amazon S3 after compile.
