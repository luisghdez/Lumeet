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


DISCOVERY_NICHES: Dict[str, Dict[str, Any]] = {
    "study_apps": {
        "id": "study_apps",
        "label": "Study apps",
        "nicheHint": "study apps, productivity, student content",
        "contentTypes": ["hook_demo", "relatable_content"],
        "hashtags": ["studytok", "studyapp", "studentlife", "productivityapp"],
        "searchQueries": ["study app", "student productivity app", "study planner app"],
    },
    "productivity_apps": {
        "id": "productivity_apps",
        "label": "Productivity apps",
        "nicheHint": "productivity apps, digital planning, creator tools",
        "contentTypes": ["hook_demo"],
        "hashtags": ["productivitytok", "productivityapp", "digitalplanner", "notiontemplate"],
        "searchQueries": ["productivity app", "notion template", "digital planner app"],
    },
    "skincare": {
        "id": "skincare",
        "label": "Skincare",
        "nicheHint": "skincare, beauty products, routines",
        "contentTypes": ["ugc_physical_product"],
        "hashtags": ["skincare", "skincareroutine", "beautytok", "skincareproducts"],
        "searchQueries": ["skincare routine", "skincare product review", "beauty product review"],
    },
    "gym_clothing": {
        "id": "gym_clothing",
        "label": "Gym clothing",
        "nicheHint": "gym clothing, activewear, fitness products",
        "contentTypes": ["ugc_physical_product"],
        "hashtags": ["gymtok", "activewear", "gymclothes", "fitnessfashion"],
        "searchQueries": ["activewear haul", "gym clothes review", "fitness outfit"],
    },
    "fashion": {
        "id": "fashion",
        "label": "Fashion",
        "nicheHint": "fashion, clothing, outfits",
        "contentTypes": ["ugc_physical_product", "relatable_content"],
        "hashtags": ["fashiontok", "outfitinspo", "clothinghaul", "grwm"],
        "searchQueries": ["clothing haul", "outfit ideas", "fashion finds"],
    },
    "relatable_student": {
        "id": "relatable_student",
        "label": "Relatable student",
        "nicheHint": "student life, relatable school content",
        "contentTypes": ["relatable_content"],
        "hashtags": ["studentlife", "studytok", "schooltok", "collegelife"],
        "searchQueries": ["student life relatable", "college life relatable", "school relatable"],
    },
    "trending_audio_dance": {
        "id": "trending_audio_dance",
        "label": "Trending audio and dance",
        "nicheHint": "trending audio, dance, easy one-scene formats",
        "contentTypes": ["trending_audio_dance"],
        "hashtags": ["dancechallenge", "trendingaudio", "tiktokdance", "trend"],
        "searchQueries": ["trending dance", "dance trend", "easy tiktok trend"],
    },
}


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


def _run_apify_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not APIFY_TOKEN:
        raise TikTokOrganizerError(
            "Missing APIFY_TOKEN. Add it to backend/.env to fetch real TikTok account data.",
            status_code=503,
        )

    actor_ref = quote(APIFY_TIKTOK_ACTOR_ID.replace("/", "~"), safe="~")
    base_url = f"https://api.apify.com/v2/acts/{actor_ref}/run-sync-get-dataset-items"
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


def _base_metadata_payload(max_items: int, results_per_page: int) -> Dict[str, Any]:
    bounded_max = max(1, min(int(max_items or results_per_page or 1), 1000))
    bounded_per_page = max(1, min(int(results_per_page or bounded_max), 200))
    return {
        "resultsPerPage": bounded_per_page,
        "maxItems": bounded_max,
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadSlideshowImages": False,
        "proxyConfiguration": {"useApifyProxy": True},
    }


def _run_apify_actor(handle: str, max_items: int) -> List[Dict[str, Any]]:
    payload = {
        **_base_metadata_payload(max_items, max_items),
        "profiles": [handle],
    }
    return _run_apify_payload(payload)


def list_discovery_niches() -> List[Dict[str, Any]]:
    return [
        {
            "id": config["id"],
            "label": config["label"],
            "nicheHint": config["nicheHint"],
            "contentTypes": config["contentTypes"],
            "hashtags": config["hashtags"],
            "searchQueries": config["searchQueries"],
        }
        for config in DISCOVERY_NICHES.values()
    ]


def build_discovery_payload(config: Dict[str, Any], max_items: int, results_per_page: int) -> Dict[str, Any]:
    return {
        **_base_metadata_payload(max_items, results_per_page),
        "hashtags": config.get("hashtags") or [],
        "searchQueries": config.get("searchQueries") or [],
        "searchSection": "/video",
        "videoSearchSorting": "MOST_RELEVANT",
        "videoSearchDateFilter": "LAST_3_MONTHS",
    }


def _posted_timestamp(value: Any) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return int(parsed.timestamp())
    except (TypeError, ValueError):
        return 0


def _query_matches(video: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, List[str]]:
    caption = (video.get("caption") or "").lower()
    tags = [str(tag).lower().lstrip("#") for tag in video.get("hashtags") or []]
    matched_hashtags = [
        tag for tag in config.get("hashtags", [])
        if tag.lower().lstrip("#") in tags or f"#{tag.lower().lstrip('#')}" in caption
    ]
    matched_queries = [
        query for query in config.get("searchQueries", [])
        if all(part in caption for part in query.lower().split())
    ]
    return {
        "hashtags": matched_hashtags,
        "queries": matched_queries,
    }


def _reason_for_creator(display_name: str, niche_label: str, video_count: int, hashtags: List[str], queries: List[str]) -> str:
    matches = hashtags[:3] or queries[:3]
    match_text = ", ".join(matches) if matches else niche_label
    name = display_name or "Creator"
    return f"{name} matched {video_count} {niche_label} videos around {match_text}."


def _rank_discovered_accounts(
    videos: List[Dict[str, Any]],
    config: Dict[str, Any],
    limit: int,
) -> List[Dict[str, Any]]:
    creators: Dict[str, Dict[str, Any]] = {}
    for video in videos:
        handle = (video.get("creatorHandle") or "").strip().lstrip("@")
        if not handle or handle.lower() in {"discovery", "unknown"}:
            continue

        key = handle.lower()
        metrics = video.get("metrics") or {}
        views = int(metrics.get("views") or 0)
        likes = int(metrics.get("likes") or 0)
        posted_at = _posted_timestamp(video.get("postedAt"))
        matches = _query_matches(video, config)
        creator = creators.setdefault(key, {
            "handle": handle,
            "displayName": video.get("creatorDisplayName") or "",
            "niche": config["id"],
            "nicheHint": config["nicheHint"],
            "accountType": (config.get("contentTypes") or [""])[0],
            "score": 0,
            "videoCount": 0,
            "totalViews": 0,
            "totalLikes": 0,
            "latestPostedAt": 0,
            "matchedHashtags": set(),
            "matchedQueries": set(),
            "sampleVideoUrls": [],
        })
        creator["videoCount"] += 1
        creator["totalViews"] += views
        creator["totalLikes"] += likes
        creator["latestPostedAt"] = max(creator["latestPostedAt"], posted_at)
        creator["matchedHashtags"].update(matches["hashtags"])
        creator["matchedQueries"].update(matches["queries"])
        if video.get("url") and len(creator["sampleVideoUrls"]) < 3:
            creator["sampleVideoUrls"].append(video["url"])
        if not creator["displayName"] and video.get("creatorDisplayName"):
            creator["displayName"] = video["creatorDisplayName"]

    ranked: List[Dict[str, Any]] = []
    now_ts = int(datetime.now(timezone.utc).timestamp())
    for creator in creators.values():
        video_count = creator["videoCount"]
        avg_views = creator["totalViews"] / max(video_count, 1)
        avg_likes = creator["totalLikes"] / max(video_count, 1)
        days_since_latest = (now_ts - creator["latestPostedAt"]) / 86400 if creator["latestPostedAt"] else 365
        recency_bonus = 12 if days_since_latest <= 14 else (6 if days_since_latest <= 90 else 0)
        hashtag_bonus = min(len(creator["matchedHashtags"]) * 5, 20)
        query_bonus = min(len(creator["matchedQueries"]) * 4, 16)
        score = (
            min(video_count * 14, 42)
            + min(avg_views / 10000, 18)
            + min(avg_likes / 1000, 12)
            + recency_bonus
            + hashtag_bonus
            + query_bonus
        )
        matched_hashtags = sorted(creator["matchedHashtags"])
        matched_queries = sorted(creator["matchedQueries"])
        ranked.append({
            "id": f"{config['id']}_{creator['handle'].lower()}",
            "handle": creator["handle"],
            "displayName": creator["displayName"],
            "niche": creator["niche"],
            "nicheHint": creator["nicheHint"],
            "accountType": creator["accountType"],
            "score": round(score, 1),
            "reason": _reason_for_creator(
                creator["displayName"],
                config["label"],
                video_count,
                matched_hashtags,
                matched_queries,
            ),
            "matchedHashtags": matched_hashtags,
            "matchedQueries": matched_queries,
            "sampleVideoUrls": creator["sampleVideoUrls"],
            "metricsSummary": {
                "videoCount": video_count,
                "avgViews": round(avg_views),
                "avgLikes": round(avg_likes),
                "latestPostedAt": creator["latestPostedAt"],
            },
            "discoveredAt": _utc_now_iso(),
        })

    ranked.sort(key=lambda item: item.get("score", 0), reverse=True)
    return ranked[:limit]


def discover_tiktok_accounts_for_niche(
    niche: str,
    limit: int = 25,
    videos_per_source: int = 20,
) -> Dict[str, Any]:
    niche_key = (niche or "").strip().lower()
    config = DISCOVERY_NICHES.get(niche_key)
    if not config:
        raise TikTokOrganizerError(f"Unsupported discovery niche: {niche}", 404)
    provider = (TIKTOK_PROVIDER or "apify").strip().lower()
    if provider != "apify":
        raise TikTokOrganizerError(f"Unsupported TikTok provider: {TIKTOK_PROVIDER}", 503)

    bounded_limit = max(1, min(int(limit or 25), 50))
    bounded_per_source = max(1, min(int(videos_per_source or 20), 50))
    source_count = len(config.get("hashtags") or []) + len(config.get("searchQueries") or [])
    max_items = max(bounded_limit, bounded_per_source * max(source_count, 1))
    payload = build_discovery_payload(config, max_items=max_items, results_per_page=bounded_per_source)
    provider_items = _run_apify_payload(payload)
    normalized = [
        video for video in (_normalize_video(item, "discovery") for item in provider_items)
        if video is not None
    ]
    videos = _dedupe_videos(normalized)
    accounts = _rank_discovered_accounts(videos, config, bounded_limit)
    return {
        "niche": config["id"],
        "nicheLabel": config["label"],
        "nicheHint": config["nicheHint"],
        "provider": provider,
        "createdAt": _utc_now_iso(),
        "counts": {
            "providerItems": len(provider_items),
            "videos": len(videos),
            "accounts": len(accounts),
        },
        "accounts": accounts,
        "providerInput": {
            "hashtags": payload.get("hashtags") or [],
            "searchQueries": payload.get("searchQueries") or [],
            "resultsPerPage": payload.get("resultsPerPage"),
            "maxItems": payload.get("maxItems"),
        },
    }


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
