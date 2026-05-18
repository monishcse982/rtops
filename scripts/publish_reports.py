from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = PROJECT_ROOT / "reports"
DEFAULT_BUCKET = os.getenv("REPORTS_S3_BUCKET", "test-reports")
DEFAULT_ENDPOINT = os.getenv(
    "AWS_ENDPOINT_URL_S3",
    os.getenv("REPORTS_S3_ENDPOINT", "http://localhost:9000"),
)
DEFAULT_ENVIRONMENT = os.getenv("REPORTS_ENVIRONMENT", "local")

REPORT_CONFIG: dict[str, dict[str, Any]] = {
    "functional": {
        "root": REPORTS_ROOT / "allure-report",
        "entrypoint": "index.html",
        "prefix": "functional_reports",
    },
    "performance": {
        "root": REPORTS_ROOT / "locust" / "local",
        "entrypoint": "report.html",
        "prefix": "perf_reports",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish generated functional or performance reports to S3-compatible storage."
    )
    parser.add_argument("report_type", choices=sorted(REPORT_CONFIG))
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Explicit report directory to publish. Defaults to the latest timestamped report directory.",
    )
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="Target bucket name.")
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help="S3-compatible endpoint, for example http://localhost:9000.",
    )
    parser.add_argument(
        "--environment",
        default=DEFAULT_ENVIRONMENT,
        help="Environment label to store in report metadata.",
    )
    parser.add_argument(
        "--skip-latest",
        action="store_true",
        help="Upload only the timestamped run path and skip refreshing the latest pointer.",
    )
    return parser.parse_args()


def newest_timestamped_dir(root: Path) -> Path:
    if not root.exists():
        raise FileNotFoundError(f"Report root does not exist: {root}")

    candidates = [path for path in root.iterdir() if path.is_dir() and path.name != "current"]
    if not candidates:
        raise FileNotFoundError(f"No timestamped report directories found under: {root}")

    return sorted(candidates, key=lambda path: path.name)[-1]


def resolve_source_dir(report_type: str, source_dir: Path | None) -> Path:
    if source_dir is not None:
        resolved = source_dir if source_dir.is_absolute() else PROJECT_ROOT / source_dir
        if not resolved.exists():
            raise FileNotFoundError(f"Report directory does not exist: {resolved}")
        return resolved

    return newest_timestamped_dir(REPORT_CONFIG[report_type]["root"])


def resolve_metadata(report_type: str, source_dir: Path, environment: str) -> dict[str, Any]:
    entrypoint = REPORT_CONFIG[report_type]["entrypoint"]
    entrypoint_path = source_dir / entrypoint
    if not entrypoint_path.exists():
        raise FileNotFoundError(f"Expected report entrypoint does not exist: {entrypoint_path}")

    run_id = source_dir.name
    metadata: dict[str, Any] = {
        "type": report_type,
        "run_id": run_id,
        "timestamp": run_id,
        "environment": environment,
        "entrypoint": entrypoint,
        "source_dir": str(source_dir.relative_to(PROJECT_ROOT)),
        "branch": git_output(["git", "branch", "--show-current"]),
        "commit": git_output(["git", "rev-parse", "HEAD"]),
    }
    return metadata


def git_output(cmd: list[str]) -> str | None:
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def stage_payload_dir(source_dir: Path, metadata: dict[str, Any]) -> Path:
    staging_root = Path(tempfile.mkdtemp(prefix="report-publish-"))
    payload_dir = staging_root / "payload"
    shutil.copytree(source_dir, payload_dir)
    (payload_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return payload_dir


def build_s3_client(endpoint: str) -> Any:
    try:
        import boto3
        from botocore.client import Config
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for report publishing. Install project dependencies so the "
            "publisher can use the S3-compatible MinIO endpoint."
        ) from exc

    access_key, secret_key = required_credentials()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )


def parse_endpoint(endpoint: str) -> tuple[str, bool]:
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid MINIO_ENDPOINT value: {endpoint}")
    return parsed.netloc, parsed.scheme == "https"


def required_credentials() -> tuple[str, str]:
    access_key = (
        os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("REPORTS_S3_ACCESS_KEY")
        or os.getenv("MINIO_ACCESS_KEY")
        or os.getenv("MINIO_ROOT_USER")
    )
    secret_key = (
        os.getenv("AWS_SECRET_ACCESS_KEY")
        or os.getenv("REPORTS_S3_SECRET_KEY")
        or os.getenv("MINIO_SECRET_KEY")
        or os.getenv("MINIO_ROOT_PASSWORD")
    )
    if not access_key or not secret_key:
        raise RuntimeError(
            "Missing S3 credentials. Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or the "
            "report-specific overrides for the S3-compatible endpoint."
        )
    return access_key, secret_key


def ensure_bucket(client: Any, bucket: str) -> None:
    from botocore.exceptions import ClientError

    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)


def upload_payload(
    client: Any,
    payload_dir: Path,
    bucket: str,
    prefix: str,
    *,
    remove: bool,
) -> None:
    if remove:
        clear_prefix(client, bucket, prefix)

    for path in sorted(payload_dir.rglob("*")):
        if path.is_dir():
            continue
        key = f"{prefix}/{path.relative_to(payload_dir).as_posix()}"
        client.upload_file(str(path), bucket, key)


def clear_prefix(client: Any, bucket: str, prefix: str) -> None:
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix}/"):
        contents = page.get("Contents", [])
        if not contents:
            continue
        client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
        )


def print_summary(report_type: str, bucket: str, endpoint: str, run_id: str) -> None:
    parsed = urlparse(endpoint)
    base_prefix = REPORT_CONFIG[report_type]["prefix"]
    base_url = f"{parsed.scheme}://{parsed.netloc}/{bucket}/{base_prefix}"
    print(f"Published {report_type} report run: {run_id}")
    print(f"Timestamped prefix: {base_url}/{run_id}/")
    print(f"Latest prefix: {base_url}/latest/")


def main() -> int:
    args = parse_args()
    source_dir = resolve_source_dir(args.report_type, args.source_dir)
    metadata = resolve_metadata(args.report_type, source_dir, args.environment)
    payload_dir = stage_payload_dir(source_dir, metadata)
    client = build_s3_client(args.endpoint)
    ensure_bucket(client, args.bucket)

    base_prefix = REPORT_CONFIG[args.report_type]["prefix"]
    timestamped_prefix = f"{base_prefix}/{metadata['run_id']}"
    upload_payload(client, payload_dir, args.bucket, timestamped_prefix, remove=False)

    if not args.skip_latest:
        latest_prefix = f"{base_prefix}/latest"
        upload_payload(client, payload_dir, args.bucket, latest_prefix, remove=True)

    print_summary(args.report_type, args.bucket, args.endpoint, metadata["run_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
