"""
Service layer for Late API integration.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from config import (
    LATE_ALLOW_MISSING_API_KEY,
    LATE_API_BASE_URL,
    LATE_API_KEY,
    LATE_REQUEST_TIMEOUT_SEC,
    PUBLIC_BACKEND_BASE_URL,
)
from late_client import LateApiError, LateClient


class LateServiceError(Exception):
    """Domain-level error used by API handlers."""

    def __init__(self, status_code: int, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.details = details or {}


class LateService:
    def __init__(self):
        self._session_profiles: Dict[str, str] = {}
        self._client: Optional[LateClient] = None

    def _client_or_error(self) -> LateClient:
        if self._client is not None:
            return self._client
        if not LATE_API_KEY:
            if LATE_ALLOW_MISSING_API_KEY:
                raise LateServiceError(
                    503,
                    "LATE_API_KEY is not configured. Add it to your backend environment.",
                )
            raise LateServiceError(
                500,
                "Late API is not configured server-side (missing LATE_API_KEY).",
            )
        self._client = LateClient(
            base_url=LATE_API_BASE_URL,
            api_key=LATE_API_KEY,
            timeout_sec=LATE_REQUEST_TIMEOUT_SEC,
        )
        return self._client

    def _map_error(self, exc: LateApiError) -> LateServiceError:
        return LateServiceError(
            status_code=exc.status_code,
            message=exc.message,
            details=exc.details,
        )

    def create_profile(self, session_id: str, name: str, description: str = "") -> Dict[str, Any]:
        client = self._client_or_error()
        try:
            resp = client.create_profile(name=name, description=description or None)
        except LateApiError as exc:
            raise self._map_error(exc) from exc
        profile = resp.get("profile", {})
        profile_id = profile.get("_id")
        if profile_id:
            self._session_profiles[session_id] = profile_id
        return resp

    def get_profile_id_for_session(self, session_id: str) -> Optional[str]:
        return self._session_profiles.get(session_id)

    def get_connect_url(
        self,
        session_id: str,
        platform: str,
        profile_id: Optional[str] = None,
        redirect_url: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        client = self._client_or_error()
        resolved_profile_id = profile_id or self.get_profile_id_for_session(session_id)
        if not resolved_profile_id:
            raise LateServiceError(400, "Missing profileId. Create a profile first.")
        try:
            return client.get_connect_url(
                platform=platform,
                profile_id=resolved_profile_id,
                redirect_url=redirect_url,
                state=state,
            )
        except LateApiError as exc:
            raise self._map_error(exc) from exc

    def list_accounts(self, session_id: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
        client = self._client_or_error()
        resolved_profile_id = profile_id or self.get_profile_id_for_session(session_id)
        try:
            return client.list_accounts(profile_id=resolved_profile_id)
        except LateApiError as exc:
            raise self._map_error(exc) from exc

    @staticmethod
    def _validate_scheduling_fields(
        *,
        scheduled_for: Optional[str],
        publish_now: bool,
        timezone: Optional[str],
    ) -> None:
        if scheduled_for and publish_now:
            raise LateServiceError(400, "Use either scheduledFor or publishNow, not both.")
        if scheduled_for:
            try:
                datetime.fromisoformat(scheduled_for.replace("Z", "+00:00"))
            except ValueError as exc:
                raise LateServiceError(400, "scheduledFor must be an ISO datetime.") from exc
            if not timezone:
                raise LateServiceError(400, "timezone is required when scheduledFor is set.")

    @staticmethod
    def _normalize_media_urls(
        *,
        media_urls: Optional[List[str]] = None,
        include_result_video: bool = False,
        job_id: Optional[str] = None,
    ) -> List[str]:
        normalized = [u for u in (media_urls or []) if u]
        if include_result_video and job_id:
            base = PUBLIC_BACKEND_BASE_URL.rstrip("/")
            normalized.append(f"{base}/api/jobs/{job_id}/result")
        # Keep insertion order while deduplicating.
        return list(dict.fromkeys(normalized))

    def create_post(
        self,
        session_id: str,
        *,
        content: str,
        platforms: List[Dict[str, str]],
        profile_id: Optional[str] = None,
        scheduled_for: Optional[str] = None,
        publish_now: bool = False,
        timezone: Optional[str] = None,
        media_urls: Optional[List[str]] = None,
        include_result_video: bool = False,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        del session_id  # Reserved for future multi-tenant persistence.

        if not content or not content.strip():
            raise LateServiceError(400, "content is required.")
        if not platforms:
            raise LateServiceError(400, "At least one platform target is required.")

        self._validate_scheduling_fields(
            scheduled_for=scheduled_for,
            publish_now=publish_now,
            timezone=timezone,
        )

        media_list = self._normalize_media_urls(
            media_urls=media_urls,
            include_result_video=include_result_video,
            job_id=job_id,
        )

        payload: Dict[str, Any] = {
            "content": content.strip(),
            "platforms": platforms,
        }
        if profile_id:
            payload["profileId"] = profile_id
        if scheduled_for:
            payload["scheduledFor"] = scheduled_for
        if publish_now:
            payload["publishNow"] = True
        if timezone:
            payload["timezone"] = timezone
        if media_list:
            # Pass both common keys for compatibility across API revisions.
            payload["mediaUrls"] = media_list
            payload["media"] = [{"url": url} for url in media_list]

        client = self._client_or_error()
        try:
            return client.create_post(payload)
        except LateApiError as exc:
            raise self._map_error(exc) from exc


late_service = LateService()
