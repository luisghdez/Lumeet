"""
Provider-backed TikTok account metadata extraction for the organizer MVP.
"""

from __future__ import annotations

import hashlib
import json
import re
import socket
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from config import (
    APIFY_TIKTOK_ACTOR_ID,
    APIFY_TOKEN,
    TIKTOK_PROVIDER,
    TIKTOK_SCAN_TIMEOUT_SEC,
)


class TikTokOrganizerError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_handle(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise TikTokOrganizerError("Enter a TikTok handle or profile URL.")

    if value.startswith("@"):
        value = value[1:]

    if "tiktok.com" in value.lower():
        parsed = urlparse(value if "://" in value else f"https://{value}")
        parts = [part for part in parsed.path.split("/") if part]
        handle_part = next((part for part in parts if part.startswith("@")), parts[0] if parts else "")
        value = handle_part.lstrip("@")

    value = value.strip().strip("/")
    if not re.match(r"^[A-Za-z0-9._]{2,64}$", value):
        raise TikTokOrganizerError("TikTok handle must be 2-64 letters, numbers, dots, or underscores.")
    return value


def _normalize_url(raw_url: str) -> str:
    raw = (raw_url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    netloc = parsed.netloc.lower()
    if netloc == "m.tiktok.com":
        netloc = "www.tiktok.com"
    path = re.sub(r"/+$", "", parsed.path)
    return urlunparse((parsed.scheme or "https", netloc, path, "", "", ""))


def _first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _nested(data: Dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    try:
        if value in (None, ""):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _extract_hashtags(item: Dict[str, Any], caption: str) -> List[str]:
    raw_tags = item.get("hashtags") or item.get("challenges") or []
    tags: List[str] = []
    if isinstance(raw_tags, list):
        for tag in raw_tags:
            if isinstance(tag, str):
                value = tag
            elif isinstance(tag, dict):
                value = _first_value(tag.get("name"), tag.get("title"), tag.get("hashtagName"))
            else:
                value = None
            if value:
                tags.append(str(value).strip().lstrip("#"))

    for match in re.findall(r"#([\w.]+)", caption or ""):
        tags.append(match.strip().lstrip("#"))

    seen = set()
    deduped: List[str] = []
    for tag in tags:
        key = tag.lower()
        if tag and key not in seen:
            deduped.append(tag)
            seen.add(key)
    return deduped


def _build_video_url(item: Dict[str, Any], handle: str) -> str:
    raw_url = _first_value(
        item.get("webVideoUrl"),
        item.get("url"),
        item.get("shareUrl"),
        item.get("videoUrl"),
        item.get("videoWebUrl"),
    )
    if raw_url:
        return _normalize_url(str(raw_url))

    video_id = _first_value(item.get("id"), item.get("videoId"), _nested(item, "video", "id"))
    creator = _first_value(
        _nested(item, "authorMeta", "name"),
        _nested(item, "author", "uniqueId"),
        handle,
    )
    if video_id and creator:
        return _normalize_url(f"https://www.tiktok.com/@{str(creator).lstrip('@')}/video/{video_id}")
    return ""


def _normalize_video(item: Dict[str, Any], fallback_handle: str) -> Optional[Dict[str, Any]]:
    caption = str(_first_value(item.get("text"), item.get("desc"), item.get("caption"), "") or "")
    url = _build_video_url(item, fallback_handle)
    if not url:
        return None

    creator_handle = str(_first_value(
        _nested(item, "authorMeta", "name"),
        _nested(item, "authorMeta", "uniqueId"),
        _nested(item, "author", "uniqueId"),
        fallback_handle,
    ) or fallback_handle).lstrip("@")

    duration = _coerce_float(_first_value(
        _nested(item, "videoMeta", "duration"),
        _nested(item, "video", "duration"),
        item.get("duration"),
        item.get("durationSec"),
    ))

    thumbnail_url = _first_value(
        _nested(item, "videoMeta", "coverUrl"),
        _nested(item, "videoMeta", "dynamicCoverUrl"),
        _nested(item, "video", "cover"),
        item.get("coverUrl"),
        item.get("thumbnailUrl"),
    )
    source_media_url = _first_value(
        _nested(item, "videoMeta", "downloadAddr"),
        _nested(item, "videoMeta", "playAddr"),
        _nested(item, "videoMeta", "videoUrl"),
        _nested(item, "video", "downloadAddr"),
        _nested(item, "video", "playAddr"),
        item.get("downloadAddr"),
        item.get("playAddr"),
        item.get("mediaUrl"),
        item.get("videoUrl"),
    )

    metrics = {
        "views": _coerce_int(_first_value(item.get("playCount"), item.get("viewCount"), _nested(item, "stats", "playCount"))),
        "likes": _coerce_int(_first_value(item.get("diggCount"), item.get("likeCount"), _nested(item, "stats", "diggCount"))),
        "comments": _coerce_int(_first_value(item.get("commentCount"), _nested(item, "stats", "commentCount"))),
        "shares": _coerce_int(_first_value(item.get("shareCount"), _nested(item, "stats", "shareCount"))),
    }

    normalized_url = _normalize_url(url)
    stable_id = hashlib.sha1(normalized_url.encode("utf-8")).hexdigest()[:16]
    return {
        "id": stable_id,
        "platform": "tiktok",
        "url": normalized_url,
        "normalizedUrl": normalized_url,
        "creatorHandle": creator_handle,
        "creatorDisplayName": _first_value(_nested(item, "authorMeta", "nickName"), _nested(item, "author", "nickname"), ""),
        "caption": caption,
        "hashtags": _extract_hashtags(item, caption),
        "durationSec": duration,
        "thumbnailUrl": str(thumbnail_url) if thumbnail_url else "",
        "sourceMediaUrl": str(source_media_url) if source_media_url else "",
        "postedAt": _first_value(item.get("createTimeISO"), item.get("createdAt"), item.get("createTime")),
        "metrics": metrics,
        "providerVideoId": str(_first_value(item.get("id"), item.get("videoId"), "")),
    }


def _dedupe_videos(videos: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for video in videos:
        key = video.get("normalizedUrl") or video.get("url")
        if not key or key in seen:
            continue
        deduped.append(video)
        seen.add(key)
    return deduped


def _run_apify_actor(handle: str, max_items: int) -> List[Dict[str, Any]]:
    if not APIFY_TOKEN:
        raise TikTokOrganizerError(
            "Missing APIFY_TOKEN. Add it to backend/.env to fetch real TikTok account data.",
            status_code=503,
        )

    actor_ref = quote(APIFY_TIKTOK_ACTOR_ID.replace("/", "~"), safe="~")
    base_url = f"https://api.apify.com/v2/acts/{actor_ref}/run-sync-get-dataset-items"
    payload = {
        "profiles": [handle],
        "resultsPerPage": max_items,
        "maxItems": max_items,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadSlideshowImages": False,
        "proxyConfiguration": {"useApifyProxy": True},
    }
    params = {
        "token": APIFY_TOKEN,
        "clean": "true",
        "format": "json",
    }
    url = f"{base_url}?{urlencode(params)}"
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=TIKTOK_SCAN_TIMEOUT_SEC) as response:
            status_code = response.status
            raw_body = response.read().decode("utf-8")
    except socket.timeout as exc:
        raise TikTokOrganizerError("TikTok provider timed out. Try a smaller max video count.", 504) from exc
    except HTTPError as exc:
        status_code = exc.code
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        if status_code == 401:
            raise TikTokOrganizerError("Apify rejected APIFY_TOKEN. Check the token in backend/.env.", 503) from exc
        if status_code == 429:
            raise TikTokOrganizerError("TikTok provider rate limit reached. Try again later.", 429) from exc
        raise TikTokOrganizerError(f"TikTok provider failed ({status_code}): {detail}", 502) from exc
    except URLError as exc:
        raise TikTokOrganizerError(f"TikTok provider request failed: {exc}", 502) from exc

    if status_code >= 400:
        raise TikTokOrganizerError(f"TikTok provider failed ({status_code}): {raw_body[:400]}", 502)

    try:
        data = json.loads(raw_body or "[]")
    except json.JSONDecodeError as exc:
        raise TikTokOrganizerError("TikTok provider returned an invalid JSON response.", 502) from exc
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        items = data.get("items") or data.get("data") or []
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def scan_tiktok_account(account: str, max_items: int = 30) -> Dict[str, Any]:
    handle = _clean_handle(account)
    bounded_max = max(1, min(int(max_items or 30), 100))
    provider = (TIKTOK_PROVIDER or "apify").strip().lower()
    if provider != "apify":
        raise TikTokOrganizerError(f"Unsupported TikTok provider: {TIKTOK_PROVIDER}", 503)

    provider_items = _run_apify_actor(handle, bounded_max)
    normalized = [
        video for video in (_normalize_video(item, handle) for item in provider_items)
        if video is not None
    ]
    videos = _dedupe_videos(normalized)

    return {
        "scanId": f"tt_{uuid.uuid4().hex[:12]}",
        "status": "completed",
        "platform": "tiktok",
        "provider": provider,
        "accountInput": account,
        "creatorHandle": handle,
        "maxItems": bounded_max,
        "createdAt": _utc_now_iso(),
        "counts": {
            "providerItems": len(provider_items),
            "videos": len(videos),
            "duplicatesRemoved": max(0, len(normalized) - len(videos)),
        },
        "videos": videos,
    }
