# Persistence Upgrade

Run `python -m cli.yare storage init` with an administrator connection before using the updated runtime. On October 12, the two additive history tables and receipt backfill were applied to the existing database: 40 receipts had 40 events, with no receipt missing an event. Existing agent records were preserved.

Schema changes add `yare_run_snapshots` (one immutable packet per run/state pair) and `yare_events` (one event per receipt). Initialization backfills events from existing receipts and state rows; it does not manufacture additional agent runs. Historical events may only have the state available in legacy storage rather than a full original packet.

Normal compile no longer runs cluster settings or DDL. Runtime inserts use `ON CONFLICT DO NOTHING`; timeline/diff read events rather than deduplicated state rows. A repeated state therefore still has a new event and receipt. The original run table remains for compatibility, not as the latest-state pointer.

Use a separate runtime database role with SELECT and INSERT on Yare tables. Only the setup role should need schema/cluster-setting privileges. An October 12 temporary-role probe verified actual SELECT/INSERT, two same-state history events and denied UPDATE; its data was rolled back and its role removed. The database currently grants CREATE on the public schema to PUBLIC, so a runtime role inherits table-creation permission. This boundary is not closed: changing that shared grant needs approval and a review of existing setup users. A probe-created table was removed after confirming temporary-role ownership.

The database transaction runs before final local exports are replaced. Each local file uses temporary-file replacement. This is not a single transaction across three files, CockroachDB and S3. Output reports which destinations succeeded; a database commit can be unconfirmed after a connection failure. Archive failure is reported separately, preserving saved memory/local files for retry.

Search accepts `--task` to filter both vector and lexical candidates before their limit. Six labelled live queries returned the expected section first for approval, modified files, unfinished and unresolved work. That verifies those queries against existing memory on one task; it does not establish general semantic quality or a broad benchmark score.
