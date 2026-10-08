# Read-Only A/B Demo

Status: locally verified on October 8, 2026. Not deployed or enabled for
anonymous public access.

The existing `site/demo.html` layout now reads `/api/verified-handoff`. The
endpoint selects only the two run, state-hash, and receipt-hash combinations
listed in `site/public-upgrade-handoff.json`. They are the post-run,
access-bearing CockroachDB records documented in
`docs/NEMOTRON_BOUNDARY_RESULT.md`.

The endpoint also requires access evidence in each pinned receipt. The
response contains those record identifiers, their database timestamps,
and a curated summary of the documented tests and access result. It does not
return raw state JSON, artifacts, receipt JSON, source files, or credentials.
The result is one isolated coding task: A left two full-suite failures, and
fresh B finished with six tests passing. The OpenShell access result applies
to the sandboxed task-source snapshot. It is not a broad benchmark score.

## Local Setup

From `site/`, provide `YARE_DATABASE_URL` and, when needed for the CockroachDB
certificate chain, `YARE_DATABASE_CA_PEM` through private shell environment
variables. Do not put their values in source files or shell history. Then set:

```powershell
$env:YARE_PUBLIC_UPGRADE_ENABLED = "true"
$env:YARE_PUBLIC_MODEL_ENABLED = "false"
vercel dev
```

Open `/demo` on the local Vercel URL and select **Load verified handoff**.
Copy handoff and Download JSON use only the curated response. Without the
upgrade flag, the endpoint returns 503 before making a database connection.
The paid model endpoint remains separately disabled and is not part of this
demo.

## Verification

- A local live CockroachDB read returned both exact A/B state and receipt
  pairs; the browser rendered them after a button click.
- `python -m pytest -q tests/yare/test_yare_cli.py tests/producers`: 86 passed.
- The 18 focused Node tests, including the default-off, allowlist, and receipt
  evidence checks, passed.
- `python -m cli.yare doctor`, `node --check site/demo.js`, and
  `git diff --check` passed.
- The legacy compile demo completed. No Token Factory model call was made.

The live production `/demo` remains the earlier approved-record viewer until
the upgraded page and its hosting are explicitly reviewed for release. A
successful local read is not proof of anonymous access or availability through
December 15.
