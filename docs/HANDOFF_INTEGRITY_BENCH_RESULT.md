# Yare Handoff Integrity Bench Result

Status: PARTIAL PASS

Date: 2026-08-01

## Scope

This result documents the public proof-bench rerun from the local Codex PowerShell environment.

No secrets are included.

## Environment

- `YARE_DATABASE_URL`: not set in the current shell, user environment, or machine environment
- `YARE_S3_BUCKET`: not set in the current shell, user environment, or machine environment
- AWS credentials: unavailable in this shell
- AWS CLI: not installed
- PowerShell history contained the prior CockroachDB connection string
- CockroachDB CA cert exists at `$env:APPDATA\postgresql\root.crt`

## Commands

Default bench, with no live env vars:

```powershell
.\scripts\proof-bench.ps1
```

Result:

```text
cockroach: skipped (YARE_DATABASE_URL not set)
s3: skipped (YARE_S3_BUCKET not set)
bench: complete
```

Live CockroachDB bench, with the prior connection string passed for one run:

```powershell
.\scripts\proof-bench.ps1 -DatabaseUrl "<redacted-cockroach-url>" -S3Bucket "yare-artifacts-187691954867-us-east-2-an"
```

Result:

```text
cockroach: enabled via YARE_DATABASE_URL
storage: initialized
tables: yare_runs, yare_lead_artifacts, yare_current_states, yare_receipts, yare_memory_vectors
s3: skipped (YARE_S3_BUCKET set, but AWS credentials unavailable)
```

The live CockroachDB run also completed:

- `lead compile`
- `memory search`
- `memory timeline`
- `memory diff --latest`

Latest observed bench hash:

```text
current_state_hash: 42c2f4af915293261d6a00f81207d57686b92fae49a012dce5137fc1372429e7
```

## Interpretation

The database exists and the live CockroachDB proof path works.

The original CockroachDB skip was an environment issue: the current process did not have `YARE_DATABASE_URL`.

S3 was not rerun from this shell because AWS credentials were unavailable. The bucket name alone is not sufficient for a live S3 archive test. Prior real S3 proof remains documented in `docs/S3_SMOKE_RESULT.md`.

## Result

CockroachDB bench: PASS

S3 bench rerun: NOT RUN in this shell, blocked by missing AWS credentials

Prior S3 smoke: PASS, see `docs/S3_SMOKE_RESULT.md`
