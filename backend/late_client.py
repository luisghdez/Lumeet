"""
Thin HTTP client for the Late API.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import requests


class LateApiError(Exception):
    """Raised for any non-success Late API response."""

    def __init__(self, status_code: int, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.details = details or {}


class LateClient:
    def __init__(self, base_url: str, api_key: str, timeout_sec: int = 20):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_sec = timeout_sec

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                params=params,
                json=json,
                timeout=timeout or self.timeout_sec,
            )
        except requests.exceptions.ReadTimeout:
            raise LateApiError(
                504,
                "Late API timed out — the request was sent but the server "
                "did not respond in time. The post may have been created; "
                "check your scheduled posts.",
            )
        except requests.exceptions.ConnectionError as exc:
            raise LateApiError(502, f"Could not reach Late API: {exc}")

        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": response.text}

        if response.status_code >= 400:
            message = payload.get("detail") or payload.get("message") or "Late API error"
            raise LateApiError(response.status_code, message, payload)
        return payload

    def create_profile(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"name": name}
        if description:
            body["description"] = description
        return self._request("POST", "/profiles", json=body)

    def get_connect_url(
        self,
        platform: str,
        profile_id: str,
        *,
        redirect_url: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"profileId": profile_id}
        if redirect_url:
            params["redirectUrl"] = redirect_url
        if state:
            params["state"] = state
        return self._request("GET", f"/connect/{platform}", params=params)

    def list_accounts(self, profile_id: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if profile_id:
            params["profileId"] = profile_id
        return self._request("GET", "/accounts", params=params or None)

    def list_posts(
        self,
        *,
        profile_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if profile_id:
            params["profileId"] = profile_id
        if status:
            params["status"] = status
        if limit:
            params["limit"] = limit
        return self._request("GET", "/posts", params=params or None)

    def create_post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Use a longer timeout for post creation — Late may need to
        # download and process video/image media from the provided URLs.
        return self._request("POST", "/posts", json=payload, timeout=120)
