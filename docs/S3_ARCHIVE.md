# Amazon S3 Proof Artifact Archive

Yare can archive proof artifacts to Amazon S3 after `yare lead compile` succeeds.

S3 is archive only. CockroachDB remains the primary durable memory system of record.

## Environment

Required:

```powershell
$env:YARE_S3_BUCKET = "<bucket-name>"
```

Optional:

```powershell
$env:YARE_S3_PREFIX = "yare/"
```

If `YARE_S3_PREFIX` is unset, Yare uses `yare/`.

AWS credentials must be available to `boto3` through the normal AWS provider chain, such as:

- `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
- `AWS_PROFILE`
- SSO or role credentials already configured locally
- instance or task role credentials in AWS runtime environments

Do not commit AWS credentials or bucket secrets.

## Command

```powershell
$env:YARE_S3_BUCKET = "<bucket-name>"
$env:YARE_S3_PREFIX = "yare/"
python -m cli.yare lead compile --task "compile ai work lead state" --artifact examples/lead-artifacts/run-codex.jsonl --artifact examples/lead-artifacts/run-claude.json --artifact examples/lead-artifacts/run-gemini.jsonl
```

## Uploaded Objects

For deterministic hash `<deterministic_hash>`, Yare uploads:

- `s3://<bucket>/yare/current-states/<deterministic_hash>/current-state.json`
- `s3://<bucket>/yare/current-states/<deterministic_hash>/current-state.md`
- `s3://<bucket>/yare/current-states/<deterministic_hash>/receipt.jsonl`

The CLI prints each uploaded URI as:

```text
s3_uri: s3://<bucket>/yare/current-states/<deterministic_hash>/current-state.json
s3_uri: s3://<bucket>/yare/current-states/<deterministic_hash>/current-state.md
s3_uri: s3://<bucket>/yare/current-states/<deterministic_hash>/receipt.jsonl
```

## No Bucket Behavior

If `YARE_S3_BUCKET` is unset, Yare does not upload anything and local/CockroachDB behavior is unchanged.
