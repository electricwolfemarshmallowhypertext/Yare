# Demo App

The Yare demo is a read-only live CockroachDB memory viewer.

It lets a judge click one button and load the latest Yare handoff from the live database.

## Flow

```text
browser
-> /demo
-> /api/latest-handoff
-> CockroachDB
-> rendered live handoff
```

## Endpoint

```http
GET /api/latest-handoff
```

The endpoint reads `process.env.YARE_DATABASE_URL` on the server only. The database URL is never sent to the browser.

It performs SELECT queries only. It does not write to CockroachDB, upload files, require auth, or expose a database UI.

## Returned Fields

- `run_id`
- `task`
- `current_state_hash`
- `receipt_hash`
- `created_at`
- `what_changed`
- `what_is_true`
- `what_is_unverified`
- `contradictions`
- `human_approval_items`
- `open_loops`
- `next_clean_action`

## Vercel

Set this environment variable in the Vercel project:

```text
YARE_DATABASE_URL=postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full
```

Then redeploy and verify:

```text
https://yare-vert.vercel.app/demo
```

Click:

```text
Load latest live handoff
```

Expected status:

```text
Loaded from live CockroachDB memory
```
