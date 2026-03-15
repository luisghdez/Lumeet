"""
GCS storage helper for carousel media and generated videos.
"""

from __future__ import annotations

import mimetypes
from datetime import timedelta
from typing import Dict

from google.cloud import storage

from config import GCS_BUCKET_NAME, GCS_SIGNED_URL_TTL_SEC


class GcsStorageError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class GcsStorage:
    def __init__(self):
        if not GCS_BUCKET_NAME:
            raise GcsStorageError(500, "GCS_BUCKET_NAME is not configured.")
        self.bucket_name = GCS_BUCKET_NAME
        self.client = storage.Client()
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
