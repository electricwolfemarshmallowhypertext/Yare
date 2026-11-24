# Demo App

The Yare demo is a read-only live CockroachDB memory viewer.

It loads saved evidence from two approved records of one completed A/B coding task. It does not execute agents or select the latest arbitrary run.

## Flow

```text
browser
-> /demo
-> /api/verified-handoff
-> CockroachDB
-> saved patches, test output and compiled handoffs
```

## Endpoint

```http
GET /api/verified-handoff
```

The endpoint reads `process.env.YARE_DATABASE_URL` on the server only. The database URL is never sent to the browser.

It performs SELECT queries only. It does not write to CockroachDB, upload files, require auth, or expose a database UI.

## Returned Evidence

Each phase includes its run ID, state hash, receipt hash, creation time, saved patch, targeted test and full-suite command/output/exit code, and seven public handoff sections. B's stored assessment is labeled as an agent statement, not independent test evidence. Access results include the recorded policy decision, command exit, denial output and snapshot/policy hashes.

The server recalculates the original state, receipt and source hashes before returning selected fields. Raw artifacts, full source files, private paths and credentials are not returned. Missing or mismatched evidence fails closed. The publication list still restricts the endpoint to the exact approved A/B pairs.

These approved records were recompiled after the live coding run to include recorded access decisions in receipts. This is a read of existing evidence, not a new coding run or a fresh permission test.

## Vercel

The deployed server requires the existing database connection and publication flag:

```text
YARE_DATABASE_URL=postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full
YARE_PUBLIC_UPGRADE_ENABLED=true
```

Then redeploy and verify:

```text
https://yare-vert.vercel.app/demo
```

Click:

```text
Load verified handoff
```

Expected status:

```text
Loaded saved patches, tests and handoffs from CockroachDB
```
