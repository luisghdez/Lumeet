"""Tests for GCS credential validation."""

import json
import os

import pytest

from backend.storage_gcs import GcsStorageError, validate_gcs_credentials


class TestGcsCredentialValidation:
    def test_empty_credentials_file(self, monkeypatch, tmp_path):
        creds_path = tmp_path / "empty.json"
        creds_path.write_text("")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds_path))

        with pytest.raises(GcsStorageError, match="empty file"):
            validate_gcs_credentials()

    def test_invalid_credentials_json(self, monkeypatch, tmp_path):
        creds_path = tmp_path / "bad.json"
        creds_path.write_text("{not-json")
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds_path))

        with pytest.raises(GcsStorageError, match="not valid JSON"):
            validate_gcs_credentials()

    def test_valid_credentials_json(self, monkeypatch, tmp_path):
        creds_path = tmp_path / "good.json"
        creds_path.write_text(json.dumps({"type": "service_account", "project_id": "demo"}))
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(creds_path))

        validate_gcs_credentials()

    def test_missing_credentials_file(self, monkeypatch, tmp_path):
        missing = tmp_path / "missing.json"
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(missing))

        with pytest.raises(GcsStorageError, match="not found"):
            validate_gcs_credentials()

    def test_no_credentials_env_is_ok(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        validate_gcs_credentials()
