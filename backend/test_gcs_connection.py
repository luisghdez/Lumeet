"""
Simple manual connectivity test for Google Cloud Storage.

Usage:
    cd backend
    export GCS_BUCKET_NAME="lumeet"
    python test_gcs_connection.py

Optional:
    export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/to/service-account.json"
    python test_gcs_connection.py --bucket your-bucket --prefix lumeet/smoke --timeout 30
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError, NotFound, Forbidden


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test GCS auth + bucket access with upload/read/delete roundtrip."
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("GCS_BUCKET_NAME", "").strip(),
        help="GCS bucket name. Defaults to GCS_BUCKET_NAME env var.",
    )
    parser.add_argument(
        "--prefix",
        default=os.environ.get("GCS_TEST_PREFIX", "lumeet/smoke").strip(),
        help="Object prefix for the smoke test file.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Request timeout in seconds (default: 20).",
    )
    return parser.parse_args()


def _resolve_bucket_name(cli_bucket: str) -> str:
    if cli_bucket:
        return cli_bucket

    # Mirror existing env discovery pattern used in other connectivity tests.
    here = Path(__file__).resolve().parent
    candidates = [here / ".env", here.parent / ".env"]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            lhs, rhs = line.split("=", 1)
            if lhs.strip() != "GCS_BUCKET_NAME":
                continue
            return rhs.strip().strip("'\"")
    return ""


def main() -> int:
    args = parse_args()
    bucket_name = _resolve_bucket_name(args.bucket)

    if not bucket_name:
        print("ERROR: GCS bucket name is missing.")
        print('Set it first, e.g. export GCS_BUCKET_NAME="your-bucket"')
        print("Or add GCS_BUCKET_NAME to backend/.env or repo .env")
        return 1

    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    print(f"Bucket: {bucket_name}")
    print(
        "Auth mode: "
        + (
            f"service account file ({credentials_path})"
            if credentials_path
            else "Application Default Credentials (gcloud/user/workload identity)"
        )
    )

    object_name = f"{args.prefix.rstrip('/')}/gcs_smoke_{uuid.uuid4().hex[:10]}.txt"
    payload = f"Lumeet GCS smoke test object {uuid.uuid4().hex}\n"

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)

        print(f"Uploading object: gs://{bucket_name}/{object_name}")
        blob.upload_from_string(payload, content_type="text/plain", timeout=args.timeout)

        print("Reading object metadata...")
        blob.reload(timeout=args.timeout)
        print(f"  size={blob.size} bytes content_type={blob.content_type}")

        print("Downloading object and verifying content...")
        downloaded = blob.download_as_text(timeout=args.timeout)
        if downloaded != payload:
            print("ERROR: downloaded content does not match uploaded payload.")
            return 1

        print("Deleting object...")
        blob.delete(timeout=args.timeout)

        print("Success: GCS upload/read/delete smoke test passed.")
        return 0
    except NotFound as exc:
        print(f"GCS error: bucket or object not found ({exc}).")
    except Forbidden as exc:
        print(f"GCS error: permission denied ({exc}).")
    except GoogleAPIError as exc:
        print(f"GCS API error: {exc}")
    except Exception as exc:  # pragma: no cover - defensive fallback for manual script
        print(f"Unexpected error: {exc}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
