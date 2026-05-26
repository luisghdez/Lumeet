"""
GCS storage helper for carousel media and generated videos.
"""

from __future__ import annotations

import json
import mimetypes
import os
from datetime import timedelta
from typing import Dict

from google.cloud import storage

from config import GCS_BUCKET_NAME, GCS_SIGNED_URL_TTL_SEC


class GcsStorageError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def validate_gcs_credentials() -> None:
    """Validate GCS auth config before attempting uploads."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not creds_path:
        return

    if not os.path.isfile(creds_path):
        raise GcsStorageError(
            500,
            f"GOOGLE_APPLICATION_CREDENTIALS file not found: {creds_path}",
        )

    if os.path.getsize(creds_path) == 0:
        raise GcsStorageError(
            500,
            "GOOGLE_APPLICATION_CREDENTIALS points to an empty file "
            f"({creds_path}). Download the lumeet-backend service account key "
            "from Google Cloud Console and save it there, then restart the backend.",
        )

    try:
        with open(creds_path, encoding="utf-8") as handle:
            json.load(handle)
    except json.JSONDecodeError as exc:
        raise GcsStorageError(
            500,
            f"GOOGLE_APPLICATION_CREDENTIALS is not valid JSON ({creds_path}): {exc}",
        ) from exc


class GcsStorage:
    def __init__(self):
        if not GCS_BUCKET_NAME:
            raise GcsStorageError(500, "GCS_BUCKET_NAME is not configured.")
        validate_gcs_credentials()
        self.bucket_name = GCS_BUCKET_NAME
        try:
            self.client = storage.Client()
        except Exception as exc:
            creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
            hint = (
                f" Check GOOGLE_APPLICATION_CREDENTIALS ({creds_path})."
                if creds_path
                else " Set GOOGLE_APPLICATION_CREDENTIALS or run gcloud auth application-default login."
            )
            raise GcsStorageError(500, f"Could not initialize Google Cloud Storage client.{hint} {exc}") from exc
        self.bucket = self.client.bucket(self.bucket_name)

    def upload_file(self, local_path: str, object_name: str) -> Dict[str, str]:
        content_type, _ = mimetypes.guess_type(local_path)
        blob = self.bucket.blob(object_name)
        blob.upload_from_filename(local_path, content_type=content_type or "application/octet-stream")

        signed = self.generate_read_url(object_name)

        return {
            "bucket": self.bucket_name,
            "object": object_name,
            "url": signed,
        }

    def upload_file_public(self, local_path: str, object_name: str) -> Dict[str, str]:
        """Upload a file and return a publicly usable URL.

        Attempts to make the blob publicly readable via legacy ACL.  When the
        bucket uses **uniform bucket-level access** (which disables per-object
        ACLs) the call is expected to fail — in that case we fall back to a
        long-lived signed URL so the object is still reachable externally.

        Returns a dict with ``bucket``, ``object``, and ``url``.
        """
        content_type, _ = mimetypes.guess_type(local_path)
        blob = self.bucket.blob(object_name)
        blob.upload_from_filename(local_path, content_type=content_type or "application/octet-stream")

        # Try per-object ACL first (works for fine-grained buckets).
        try:
            blob.make_public()
            url = self.public_url(object_name)
        except Exception:
            # Bucket likely has uniform access — use a long-lived signed URL instead.
            url = self.generate_read_url(object_name)

        return {
            "bucket": self.bucket_name,
            "object": object_name,
            "url": url,
        }

    @staticmethod
    def public_url(object_name: str) -> str:
        """Return the canonical public URL for a GCS object."""
        return f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"

    def generate_read_url(self, object_name: str) -> str:
        blob = self.bucket.blob(object_name)
        # Prefer signed URL for private buckets; fall back to canonical object URL.
        try:
            return blob.generate_signed_url(
                version="v4",
                expiration=timedelta(seconds=GCS_SIGNED_URL_TTL_SEC),
                method="GET",
            )
        except Exception:
            return f"https://storage.googleapis.com/{self.bucket_name}/{object_name}"
