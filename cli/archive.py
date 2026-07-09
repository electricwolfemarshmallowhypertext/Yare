from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BUCKET_ENV = "YARE_S3_BUCKET"
PREFIX_ENV = "YARE_S3_PREFIX"
DEFAULT_PREFIX = "yare/"


class ArchiveError(RuntimeError):
    pass


def _bucket(explicit_bucket: str | None = None) -> str | None:
    value = explicit_bucket or os.environ.get(BUCKET_ENV)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _prefix(explicit_prefix: str | None = None) -> str:
    raw = explicit_prefix if explicit_prefix is not None else os.environ.get(PREFIX_ENV, DEFAULT_PREFIX)
    prefix = (raw or DEFAULT_PREFIX).strip().replace("\\", "/").strip("/")
    return f"{prefix}/" if prefix else ""


def _client(client: Any = None) -> Any:
    if client is not None:
        return client
    try:
        import boto3  # type: ignore
    except ImportError as e:
        raise ArchiveError("boto3 is required for S3 archive uploads") from e
    return boto3.client("s3")


def _upload_file(client: Any, bucket: str, path: Path, key: str) -> str:
    if not path.exists() or not path.is_file():
        raise ArchiveError(f"s3_archive_missing_file: {path}")
    client.upload_file(str(path), bucket, key)
    return f"s3://{bucket}/{key}"


def archive_lead_compile(
    *,
    packet: dict[str, Any],
    json_path: Path,
    md_path: Path,
    receipt_path: Path,
    bucket: str | None = None,
    prefix: str | None = None,
    client: Any = None,
) -> list[str]:
    target_bucket = _bucket(bucket)
    if not target_bucket:
        return []

    deterministic_hash = str(packet.get("deterministic_hash") or "").strip()
    if not deterministic_hash:
        raise ArchiveError("s3_archive_missing_deterministic_hash")

    base = f"{_prefix(prefix)}current-states/{deterministic_hash}"
    uploads = (
        (json_path, f"{base}/current-state.json"),
        (md_path, f"{base}/current-state.md"),
        (receipt_path, f"{base}/receipt.jsonl"),
    )
    s3 = _client(client)
    try:
        return [_upload_file(s3, target_bucket, path, key) for path, key in uploads]
    except ArchiveError:
        raise
    except Exception as e:
        raise ArchiveError(f"s3_archive_upload_failed: {e}") from e
