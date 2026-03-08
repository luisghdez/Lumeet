"""
Tests for Late API proxy endpoints in FastAPI.
"""

import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Make backend modules importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api import app
from late_service import LateServiceError


@pytest.fixture()
def client():
    return TestClient(app)


def test_create_profile_success(client):
    with patch("api.late_service.create_profile") as mock_create:
        mock_create.return_value = {"profile": {"_id": "prof_123", "name": "Test"}}
        resp = client.post(
            "/api/late/profiles",
            json={"sessionId": "s1", "name": "Test", "description": "Demo"},
        )
        assert resp.status_code == 200
        assert resp.json()["profile"]["_id"] == "prof_123"
        mock_create.assert_called_once()


def test_create_profile_validation_error(client):
    resp = client.post("/api/late/profiles", json={"sessionId": "s1", "name": ""})
    assert resp.status_code == 422


def test_create_profile_upstream_error(client):
    with patch("api.late_service.create_profile") as mock_create:
        mock_create.side_effect = LateServiceError(401, "Invalid Late API key")
        resp = client.post(
            "/api/late/profiles",
            json={"sessionId": "s1", "name": "Test"},
        )
        assert resp.status_code == 401
        assert "Invalid Late API key" in resp.json()["detail"]


def test_get_connect_url_success(client):
    with patch("api.late_service.get_connect_url") as mock_get:
        mock_get.return_value = {"authUrl": "https://example.com/oauth"}
        resp = client.get(
            "/api/late/connect-url",
            params={"platform": "twitter", "sessionId": "s1", "profileId": "prof_123"},
        )
        assert resp.status_code == 200
        assert resp.json()["authUrl"].startswith("https://")
        mock_get.assert_called_once()


def test_list_accounts_success(client):
    with patch("api.late_service.list_accounts") as mock_list:
        mock_list.return_value = {"accounts": [{"_id": "acc_1", "platform": "twitter"}]}
        resp = client.get("/api/late/accounts", params={"sessionId": "s1"})
        assert resp.status_code == 200
        assert len(resp.json()["accounts"]) == 1
        assert resp.json()["accounts"][0]["_id"] == "acc_1"


def test_create_post_success(client):
    with patch("api.late_service.create_post") as mock_post:
        mock_post.return_value = {"post": {"_id": "post_123"}}
        resp = client.post(
            "/api/late/posts",
            json={
                "sessionId": "s1",
                "content": "Hello world",
                "platforms": [{"platform": "twitter", "accountId": "acc_1"}],
                "publishNow": True,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["post"]["_id"] == "post_123"


def test_create_post_validation_failure(client):
    resp = client.post(
        "/api/late/posts",
        json={"sessionId": "s1", "content": "", "platforms": []},
    )
    assert resp.status_code == 422


def test_create_post_upstream_error(client):
    with patch("api.late_service.create_post") as mock_post:
        mock_post.side_effect = LateServiceError(400, "At least one platform target is required.")
        resp = client.post(
            "/api/late/posts",
            json={
                "sessionId": "s1",
                "content": "Text",
                "platforms": [{"platform": "twitter", "accountId": "acc_1"}],
            },
        )
        assert resp.status_code == 400
        assert "At least one platform target" in resp.json()["detail"]
