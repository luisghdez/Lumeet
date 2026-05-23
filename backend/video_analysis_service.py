"""
Cheap video analysis for organizer references.

Downloads source media only into a temporary file, samples low-resolution frames,
computes local motion metrics, then asks a small structured model for lean
recreation tags.
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import shutil
import subprocess
import uuid
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageDraw, ImageStat

from config import (
    APIFY_TIKTOK_ACTOR_ID,
    APIFY_TOKEN,
    OPENAI_API_KEY,
    OPENAI_TAGGING_MODEL,
    TIKTOK_SCAN_TIMEOUT_SEC,
    VIDEO_ANALYSIS_DOWNLOAD_TIMEOUT_SEC,
    VIDEO_ANALYSIS_FRAME_DIR,
    VIDEO_ANALYSIS_FRAME_WIDTH,
    VIDEO_ANALYSIS_KEEP_FRAMES,
    VIDEO_ANALYSIS_MAX_DOWNLOAD_MB,
    VIDEO_ANALYSIS_MAX_FRAMES,
    VIDEO_ANALYSIS_SAMPLE_FPS,
    VIDEO_ANALYSIS_TEMP_DIR,
)


ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class VideoAnalysisError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


FORMAT_VALUES = [
    "ugc_demo", "talking_head", "storytime", "problem_solution", "hook_demo",
    "get_ready_with_me", "mirror_body_showcase", "pose_sequence",
    "outfit_showcase", "product_showcase", "routine_demo", "tutorial_explainer",
    "comparison", "visual_showcase", "broll_montage", "trend_lip_sync", "other",
]
HOOK_VALUES = [
    "curiosity_gap", "problem_callout", "bold_claim", "social_proof", "demo_first",
    "before_after", "relatable_story", "question", "visual_body_hook",
    "visual_reveal", "aesthetic_hook", "text_overlay_hook", "no_explicit_hook",
    "other",
]
SCENE_VALUES = ["single_room", "bathroom_mirror", "bedroom", "desk_setup", "kitchen", "car", "outdoor", "screen_recording", "multi_scene", "other"]
CAMERA_VALUES = ["static", "handheld_light", "handheld_heavy", "push_in", "pull_back", "pan", "tilt", "walking_follow", "mixed"]
VISUAL_VALUES = [
    "face_to_camera", "product_in_hand", "product_closeup", "demo_steps",
    "text_overlay_heavy", "broll_montage", "mirror_shot", "screen_plus_face",
    "body_focus", "pose_sequence", "outfit_check", "visual_reveal",
    "hands_only_demo", "on_screen_text", "split_screen", "other",
]
MOTION_DIFFICULTY_VALUES = ["very_easy", "easy", "medium", "hard", "very_hard"]
MOVEMENT_AMOUNT_VALUES = ["very_low", "low", "medium", "high", "very_high"]
SCENE_ROLE_VALUES = [
    "hook", "setup_context", "demo_step", "product_showcase", "proof",
    "cta", "payoff", "transition", "broll", "other",
]
NICHE_VALUES = [
    "beauty", "fashion", "fitness", "health_wellness", "food_beverage", "home_lifestyle",
    "parenting_family", "personal_finance", "business_career", "education", "productivity",
    "tech_apps", "travel", "pets", "entertainment", "other",
]
SUB_NICHE_VALUES = {
    "beauty": ["skincare", "makeup", "haircare", "fragrance", "beauty_tools", "other"],
    "fashion": ["outfit_grwm", "try_on_haul", "styling_tips", "accessories", "shoes", "other"],
    "fitness": ["workout_routine", "weight_loss", "strength_training", "mobility", "activewear", "supplements", "other"],
    "health_wellness": ["mental_health", "sleep", "gut_health", "supplements", "self_care", "habit_building", "other"],
    "food_beverage": ["recipe", "restaurant_review", "meal_prep", "snack", "drink", "other"],
    "home_lifestyle": ["cleaning", "decor", "organization", "daily_routine", "home_product", "other"],
    "business_career": ["creator_business", "side_hustle", "job_advice", "sales_marketing", "founder_story", "other"],
    "education": ["study_tips", "language_learning", "tutorial", "explainer", "student_life", "other"],
    "tech_apps": ["app_demo", "software_tutorial", "ai_tool", "phone_setup", "gadget", "other"],
    "entertainment": ["comedy", "skit", "reaction", "storytime", "trend", "other"],
}
CONTENT_PILLAR_VALUES = [
    "relatable_lifestyle", "routine_explainer", "meal_prep_food", "product_demo", "app_demo",
    "transformation_progress", "educational_tips", "myth_busting", "review_testimonial",
    "trend_reaction", "community_story", "announcement_launch", "offer_promo",
    "behind_the_scenes", "aspirational_showcase", "visual_social_proof",
    "comparison_proof", "other",
]
PILLAR_ROLE_VALUES = [
    "trust_builder", "authority_builder", "relatability_builder", "desire_builder",
    "conversion_driver", "retention_builder",
]
ACCOUNT_ARCHETYPE_VALUES = [
    "fitness_app_creator", "fitness_lifestyle_creator", "gym_clothing_creator",
    "skincare_routine_creator", "beauty_review_creator", "study_productivity_creator",
    "education_app_creator", "wellness_habit_creator", "food_meal_prep_creator",
    "tech_tool_creator", "founder_builder_creator", "other",
]
ACCOUNT_VOICE_VALUES = [
    "expert_coach", "relatable_peer", "aspirational_friend", "funny_observer",
    "calm_teacher", "high_energy_hype", "minimal_aesthetic",
]
AUDIENCE_STAGE_VALUES = ["beginner", "intermediate", "advanced", "mixed"]
AUDIENCE_IDENTITY_VALUES = [
    "gym_beginner", "busy_student", "skincare_beginner", "weight_loss_journey",
    "muscle_gain_journey", "productivity_seeker", "budget_conscious_buyer",
    "trend_follower", "other",
]
FUNNEL_STAGE_VALUES = ["awareness", "consideration", "conversion", "retention", "reactivation"]
CAMPAIGN_USE_VALUES = [
    "top_of_funnel_reach", "organic_account_growth", "paid_ad_creative",
    "retargeting_ad", "launch_announcement", "evergreen_post", "community_nurture",
]
CONVERSION_INTENT_VALUES = ["none", "soft_sell", "medium_sell", "hard_sell"]
CTA_TYPE_VALUES = [
    "no_cta", "follow_for_more", "comment_keyword", "link_in_bio", "download_app",
    "shop_now", "try_free", "save_share",
]
PRODUCT_INTEGRATION_VALUES = [
    "none", "background_context", "mentioned_only", "shown_briefly", "demo_core",
    "before_after_driver", "testimonial_driver",
]
PRODUCT_TYPE_VALUES = ["app", "physical_product", "service", "brand", "course", "unknown"]
PRODUCT_MENTION_TYPE_VALUES = ["none", "text_overlay", "caption", "spoken", "visual_logo", "app_screen", "mixed"]
PRODUCT_VISIBILITY_VALUES = ["none", "low", "medium", "high"]
PRODUCT_FIT_VALUES = ["poor", "okay", "strong", "native"]
DEMO_DEPTH_VALUES = [
    "none", "feature_flash", "single_feature_walkthrough",
    "multi_step_walkthrough", "full_routine_integration",
]
CREATIVE_TEMPLATE_VALUES = [
    "hook_then_demo", "problem_then_solution", "day_in_the_life", "grwm",
    "routine_breakdown", "three_tips", "mistakes_to_avoid", "before_after",
    "pov_story", "testimonial_story", "trend_adaptation", "screen_recording_walkthrough",
    "body_check", "physique_showcase", "pose_sequence", "visual_showcase",
    "outfit_check", "product_try_on", "comparison_reveal", "montage",
    "voiceover_explainer", "caption_story",
]
SCRIPT_STRUCTURE_VALUES = [
    "hook_context_payoff", "problem_agitation_solution", "listicle", "story_arc",
    "demo_steps", "visual_only", "audio_only_visual", "text_overlay_only",
    "voiceover_narration", "question_answer", "hook_then_demo",
]
REPEATABILITY_VALUES = ["one_off", "repeatable_series", "template_reusable", "trend_dependent"]
PRODUCTION_COMPLEXITY_VALUES = ["low", "medium", "high"]
LOCATION_COMPLEXITY_VALUES = ["single_location", "multi_location", "public_location", "studio_like"]
ASSET_REQUIREMENT_VALUES = [
    "face", "body", "product", "app_screen", "food", "gym", "desk", "car",
    "outdoor", "mirror", "voiceover", "text_overlay",
]
TRI_STATE_VALUES = ["yes", "no", "optional"]
TEXT_OVERLAY_VALUES = ["none", "light", "heavy"]
CTA_STRENGTH_VALUES = ["none", "light", "medium", "strong"]
SCORE_FIELDS = [
    "campaign_fit_score", "account_fit_score", "repeatability_score", "viral_score",
    "conversion_potential_score", "trust_building_score", "education_value_score",
    "entertainment_value_score", "production_ease_score",
]


def _ensure_dirs() -> None:
    os.makedirs(VIDEO_ANALYSIS_TEMP_DIR, exist_ok=True)
    os.makedirs(VIDEO_ANALYSIS_FRAME_DIR, exist_ok=True)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _source_url(video_reference: Dict[str, Any]) -> str:
    url = (
        video_reference.get("sourceMediaUrl")
        or video_reference.get("mediaUrl")
        or video_reference.get("downloadUrl")
        or video_reference.get("url")
        or ""
    ).strip()
    if not url:
        raise VideoAnalysisError("Video reference has no URL to analyze.")
    return url


def _candidate_source_urls(video_reference: Dict[str, Any]) -> List[str]:
    candidates = [
        video_reference.get("sourceMediaUrl"),
        video_reference.get("mediaUrl"),
        video_reference.get("downloadUrl"),
        video_reference.get("url"),
    ]
    deduped: List[str] = []
    seen = set()
    for candidate in candidates:
        url = (candidate or "").strip()
        if not url or url in seen:
            continue
        deduped.append(url)
        seen.add(url)
    if not deduped:
        raise VideoAnalysisError("Video reference has no URL to analyze.")
    return deduped


def _download_video(video_reference: Dict[str, Any], output_path: str) -> Dict[str, Any]:
    errors = []
    candidates = _candidate_source_urls(video_reference)
    tiktok_page_url = next((url for url in candidates if _is_tiktok_page_url(url)), "")

    for url in candidates:
        try:
            downloaded_bytes = _download_direct(url, output_path)
            return {"path": output_path, "downloadedBytes": downloaded_bytes, "method": "direct", "resolvedUrl": url}
        except VideoAnalysisError as exc:
            errors.append(exc.message)
            if "returned HTML" not in exc.message and "download failed" not in exc.message.lower():
                continue
        if _is_tiktok_page_url(url):
            try:
                return _download_with_ytdlp(url, output_path)
            except VideoAnalysisError as exc:
                errors.append(exc.message)

    if tiktok_page_url:
        try:
            return _download_tiktok_with_apify(tiktok_page_url, output_path)
        except VideoAnalysisError as exc:
            errors.append(exc.message)

    detail = " | ".join(_clean_error_message(error) for error in errors if error)
    raise VideoAnalysisError(detail or "Could not download this video for analysis.", 422)


def _is_tiktok_page_url(url: str) -> bool:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc.lower()
    return "tiktok.com" in host and "/video/" in parsed.path


def _clean_error_message(message: Any) -> str:
    return ANSI_ESCAPE_RE.sub("", str(message or "")).strip()


def _download_direct(url: str, output_path: str) -> int:
    max_bytes = max(1, VIDEO_ANALYSIS_MAX_DOWNLOAD_MB) * 1024 * 1024
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; LumeetVideoAnalysis/1.0)",
            "Accept": "video/*,*/*;q=0.8",
        },
    )
    total = 0
    try:
        with urlopen(request, timeout=VIDEO_ANALYSIS_DOWNLOAD_TIMEOUT_SEC) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type.lower():
                raise VideoAnalysisError(
                    "The video URL returned HTML instead of media. Re-scan with a provider that returns direct media URLs.",
                    422,
                )
            with open(output_path, "wb") as f:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise VideoAnalysisError(
                            f"Video exceeds the {VIDEO_ANALYSIS_MAX_DOWNLOAD_MB} MB analysis limit.",
                            413,
                        )
                    f.write(chunk)
    except VideoAnalysisError:
        raise
    except HTTPError as exc:
        raise VideoAnalysisError(f"Video download failed ({exc.code}).", 422) from exc
    except URLError as exc:
        raise VideoAnalysisError(f"Video download failed: {exc}", 422) from exc
    if total <= 0:
        raise VideoAnalysisError("Downloaded video was empty.", 422)
    return total


def _download_with_ytdlp(url: str, output_path_base: str) -> Dict[str, Any]:
    max_bytes = max(1, VIDEO_ANALYSIS_MAX_DOWNLOAD_MB) * 1024 * 1024
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:
        raise VideoAnalysisError("yt-dlp is required to resolve TikTok page URLs. Install backend requirements.", 503) from exc

    outtmpl = f"{output_path_base}.%(ext)s"
    ydl_opts = {
        "format": "best[ext=mp4][height<=720]/best[ext=mp4]/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 2,
        "socket_timeout": VIDEO_ANALYSIS_DOWNLOAD_TIMEOUT_SEC,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded = info.get("requested_downloads") or []
            filepath = ""
            if downloaded and isinstance(downloaded[0], dict):
                filepath = downloaded[0].get("filepath") or downloaded[0].get("filename") or ""
            if not filepath:
                filepath = ydl.prepare_filename(info)
    except Exception as exc:
        raise VideoAnalysisError(f"yt-dlp could not resolve/download this TikTok URL: {_clean_error_message(exc)}", 422) from exc

    if not filepath or not os.path.isfile(filepath):
        candidates = [
            os.path.join(os.path.dirname(output_path_base), name)
            for name in os.listdir(os.path.dirname(output_path_base))
            if name.startswith(os.path.basename(output_path_base))
        ]
        filepath = candidates[0] if candidates else ""
    if not filepath or not os.path.isfile(filepath):
        raise VideoAnalysisError("yt-dlp finished but no video file was produced.", 422)

    size = os.path.getsize(filepath)
    if size > max_bytes:
        raise VideoAnalysisError(f"Video exceeds the {VIDEO_ANALYSIS_MAX_DOWNLOAD_MB} MB analysis limit.", 413)
    return {"path": filepath, "downloadedBytes": size, "method": "yt_dlp", "resolvedUrl": url}


def _download_tiktok_with_apify(url: str, output_path: str) -> Dict[str, Any]:
    if not APIFY_TOKEN:
        raise VideoAnalysisError("Apify fallback unavailable because APIFY_TOKEN is missing.", 503)

    actor_ref = quote(APIFY_TIKTOK_ACTOR_ID.replace("/", "~"), safe="~")
    endpoint = f"https://api.apify.com/v2/acts/{actor_ref}/run-sync-get-dataset-items"
    params = {
        "token": APIFY_TOKEN,
        "clean": "true",
        "format": "json",
    }
    payload = {
        "postURLs": [url],
        "maxItems": 1,
        "resultsPerPage": 1,
        "shouldDownloadVideos": True,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadSlideshowImages": False,
        "proxyConfiguration": {"useApifyProxy": True},
    }
    request = Request(
        f"{endpoint}?{urlencode(params)}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=max(TIKTOK_SCAN_TIMEOUT_SEC, VIDEO_ANALYSIS_DOWNLOAD_TIMEOUT_SEC)) as response:
            items = json.loads(response.read().decode("utf-8") or "[]")
    except HTTPError as exc:
        raise VideoAnalysisError(f"Apify TikTok fallback failed ({exc.code}).", 422) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise VideoAnalysisError(f"Apify TikTok fallback failed: {_clean_error_message(exc)}", 422) from exc

    if not isinstance(items, list) or not items:
        raise VideoAnalysisError("Apify TikTok fallback returned no video items.", 422)

    media_urls = _extract_media_urls(items[0], original_url=url)
    if not media_urls:
        raise VideoAnalysisError("Apify TikTok fallback returned metadata but no playable media URL.", 422)

    errors = []
    for media_url in media_urls:
        try:
            downloaded_bytes = _download_direct(media_url, output_path)
            return {
                "path": output_path,
                "downloadedBytes": downloaded_bytes,
                "method": "apify_media_url",
                "resolvedUrl": media_url,
            }
        except VideoAnalysisError as exc:
            errors.append(exc.message)

    detail = " | ".join(_clean_error_message(error) for error in errors if error)
    raise VideoAnalysisError(f"Apify returned media URLs, but none were downloadable. {detail}", 422)


def _extract_media_urls(item: Dict[str, Any], original_url: str = "") -> List[str]:
    key_hints = {"downloadaddr", "playaddr", "mediaurl", "videourl", "video_url", "downloadurl"}
    urls: List[str] = []
    seen = set()

    def visit(value: Any, key: str = "") -> None:
        lowered_key = key.lower()
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
            return
        if isinstance(value, list):
            for child_value in value:
                visit(child_value, key)
            return
        if not isinstance(value, str) or not any(hint in lowered_key for hint in key_hints):
            return
        candidate = value.strip()
        if not candidate.startswith("http"):
            return
        if candidate == original_url or _is_tiktok_page_url(candidate):
            return
        if candidate in seen:
            return
        urls.append(candidate)
        seen.add(candidate)

    visit(item)
    return urls


def _ffprobe(video_path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=avg_frame_rate,r_frame_rate,nb_frames,duration:format=duration",
        "-of", "json",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise VideoAnalysisError(f"ffprobe failed: {result.stderr[:300]}", 422)
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise VideoAnalysisError("ffprobe returned invalid JSON.", 422) from exc
    stream = (data.get("streams") or [{}])[0]
    duration = _safe_float(stream.get("duration")) or _safe_float((data.get("format") or {}).get("duration"))
    fps = _parse_fps(stream.get("avg_frame_rate")) or _parse_fps(stream.get("r_frame_rate")) or 0.0
    nb_frames = _safe_float(stream.get("nb_frames"))
    estimated_frames = int(nb_frames) if nb_frames > 0 else int(round(duration * fps)) if duration and fps else 0
    return {
        "duration_sec": round(duration, 3) if duration else 0,
        "fps": round(fps, 3) if fps else 0,
        "estimated_total_frame_count": estimated_frames,
    }


def _parse_fps(raw: Any) -> float:
    if not raw:
        return 0.0
    text = str(raw)
    if "/" in text:
        lhs, rhs = text.split("/", 1)
        den = _safe_float(rhs)
        return _safe_float(lhs) / den if den else 0.0
    return _safe_float(text)


def _sample_frames(video_path: str, frame_dir: str) -> List[str]:
    os.makedirs(frame_dir, exist_ok=True)
    fps = max(1, VIDEO_ANALYSIS_SAMPLE_FPS)
    max_frames = max(1, VIDEO_ANALYSIS_MAX_FRAMES)
    width = max(96, VIDEO_ANALYSIS_FRAME_WIDTH)
    pattern = os.path.join(frame_dir, "frame_%04d.jpg")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"fps={fps},scale={width}:-1",
        "-frames:v", str(max_frames),
        "-q:v", "5",
        pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise VideoAnalysisError(f"ffmpeg frame sampling failed: {result.stderr[:300]}", 422)
    frames = [
        os.path.join(frame_dir, name)
        for name in sorted(os.listdir(frame_dir))
        if name.lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    if not frames:
        raise VideoAnalysisError("No frames were sampled from the video.", 422)
    return frames


def _scene_metrics(video_path: str) -> Dict[str, Any]:
    """Detect real scene boundaries with PySceneDetect, matching recreation crop semantics."""
    try:
        from scenedetect import ContentDetector, SceneManager, open_video
    except Exception as exc:
        return {
            "scene_count": 1,
            "scene_change_count": 0,
            "scene_timeline": [],
            "first_scene_change_sec": None,
            "first_scene_change_frame": None,
            "first_scene_duration_sec": None,
            "can_crop_to_first_scene": False,
        **_empty_scene_similarity(),
            "scene_detection_error": f"PySceneDetect unavailable: {exc}",
        }

    try:
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=27.0))
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()
    except Exception as exc:
        return {
            "scene_count": 1,
            "scene_change_count": 0,
            "scene_timeline": [],
            "first_scene_change_sec": None,
            "first_scene_change_frame": None,
            "first_scene_duration_sec": None,
            "can_crop_to_first_scene": False,
            **_empty_scene_similarity(),
            "scene_detection_error": str(exc),
        }

    scene_count = max(1, len(scene_list))
    if scene_count <= 1:
        return {
            "scene_count": 1,
            "scene_change_count": 0,
            "scene_timeline": _scene_timeline(scene_list),
            "first_scene_change_sec": None,
            "first_scene_change_frame": None,
            "first_scene_duration_sec": None,
            "can_crop_to_first_scene": False,
            **_empty_scene_similarity(),
            "scene_detection_error": "",
        }

    first_scene_start, first_scene_end = scene_list[0]
    first_change_sec = first_scene_end.get_seconds()
    return {
        "scene_count": scene_count,
        "scene_change_count": scene_count - 1,
        "scene_timeline": _scene_timeline(scene_list),
        "first_scene_change_sec": round(first_change_sec, 3),
        "first_scene_change_frame": first_scene_end.get_frames(),
        "first_scene_duration_sec": round(first_change_sec - first_scene_start.get_seconds(), 3),
        "can_crop_to_first_scene": True,
        **_adjacent_scene_similarity(video_path, scene_list),
        "scene_detection_error": "",
    }


def _scene_timeline(scene_list: List[Any]) -> List[Dict[str, Any]]:
    timeline = []
    for idx, (start, end) in enumerate(scene_list, start=1):
        start_sec = start.get_seconds()
        end_sec = end.get_seconds()
        timeline.append({
            "scene_index": idx,
            "start_sec": round(start_sec, 3),
            "end_sec": round(end_sec, 3),
            "duration_sec": round(max(0.0, end_sec - start_sec), 3),
            "start_frame": start.get_frames(),
            "end_frame": end.get_frames(),
        })
    return timeline


def _adjacent_scene_similarity(video_path: str, scene_list: List[Any]) -> Dict[str, Any]:
    if len(scene_list) < 2:
        return _empty_scene_similarity()

    compare_dir = os.path.join(os.path.dirname(video_path), "scene_similarity")
    os.makedirs(compare_dir, exist_ok=True)
    try:
        scene_frames = []
        for idx, scene in enumerate(scene_list, start=1):
            frame_path = os.path.join(compare_dir, f"scene_{idx}.jpg")
            _extract_scene_midpoint_frame(video_path, scene, frame_path)
            scene_frames.append(frame_path)

        pairs = [
            _compare_scene_frames(scene_frames[idx], scene_frames[idx + 1], idx + 1, idx + 2)
            for idx in range(len(scene_frames) - 1)
        ]
        first_pair = pairs[0] if pairs else {}
        scores = [pair["similarity_score"] for pair in pairs if pair.get("similarity_score") is not None]
        min_pair = min(pairs, key=lambda pair: pair.get("similarity_score", 1.0)) if pairs else {}
        avg_score = sum(scores) / len(scores) if scores else None
        return {
            "scene_similarity_pairs": pairs,
            "average_adjacent_scene_similarity_score": round(avg_score, 4) if avg_score is not None else None,
            "lowest_adjacent_scene_similarity_score": min_pair.get("similarity_score"),
            "lowest_adjacent_scene_similarity_pair": {
                "from_scene": min_pair.get("from_scene"),
                "to_scene": min_pair.get("to_scene"),
            } if min_pair else None,
            "first_two_scene_similarity_score": first_pair.get("similarity_score"),
            "first_two_scene_structure_similarity_score": first_pair.get("structure_similarity_score"),
            "first_two_scene_camera_similarity_score": first_pair.get("camera_similarity_score"),
            "first_two_scene_character_similarity_score": first_pair.get("character_similarity_score"),
            "first_two_scenes_similar": first_pair.get("similar"),
            "scene_similarity_error": "",
        }
    except Exception as exc:
        return {**_empty_scene_similarity(), "scene_similarity_error": str(exc)}


def _compare_scene_frames(frame_a: str, frame_b: str, from_scene: int, to_scene: int) -> Dict[str, Any]:
    diff = _image_diff_score(frame_a, frame_b)
    structure_score = _histogram_similarity(frame_a, frame_b)
    camera_score = max(0.0, min(1.0, 1.0 - diff["full"]))
    character_score = max(0.0, min(1.0, 1.0 - diff["center"]))
    combined = (structure_score * 0.4) + (camera_score * 0.3) + (character_score * 0.3)
    return {
        "from_scene": from_scene,
        "to_scene": to_scene,
        "similarity_score": round(combined, 4),
        "structure_similarity_score": round(structure_score, 4),
        "camera_similarity_score": round(camera_score, 4),
        "character_similarity_score": round(character_score, 4),
        "similar": combined >= 0.72,
    }


def _empty_scene_similarity() -> Dict[str, Any]:
    return {
        "scene_similarity_pairs": [],
        "average_adjacent_scene_similarity_score": None,
        "lowest_adjacent_scene_similarity_score": None,
        "lowest_adjacent_scene_similarity_pair": None,
        "first_two_scene_similarity_score": None,
        "first_two_scene_structure_similarity_score": None,
        "first_two_scene_camera_similarity_score": None,
        "first_two_scene_character_similarity_score": None,
        "first_two_scenes_similar": None,
        "scene_similarity_error": "",
    }


def _extract_scene_midpoint_frame(video_path: str, scene: Any, output_path: str) -> None:
    start, end = scene
    start_sec = start.get_seconds()
    end_sec = end.get_seconds()
    timestamp = start_sec + max(0.05, (end_sec - start_sec) / 2)
    _extract_video_frame(video_path, timestamp, output_path)


def _extract_video_frame(video_path: str, timestamp: float, output_path: str) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-vf", f"scale={max(96, VIDEO_ANALYSIS_FRAME_WIDTH)}:-1",
        "-q:v", "5",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not os.path.isfile(output_path):
        raise VideoAnalysisError(f"scene frame extraction failed: {result.stderr[:200]}", 422)


def _scene_role_contact_sheet(video_path: str, scene_timeline: List[Dict[str, Any]], output_path: str) -> str:
    if len(scene_timeline) <= 1:
        return ""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    frame_dir = os.path.join(os.path.dirname(output_path), "scene_role_frames")
    os.makedirs(frame_dir, exist_ok=True)
    selected_scenes = scene_timeline[:16]
    thumbs = []
    for scene in selected_scenes:
        scene_index = scene.get("scene_index")
        start_sec = _safe_float(scene.get("start_sec"))
        end_sec = _safe_float(scene.get("end_sec"), start_sec)
        midpoint = start_sec + max(0.05, (end_sec - start_sec) / 2)
        frame_path = os.path.join(frame_dir, f"scene_{scene_index}.jpg")
        _extract_video_frame(video_path, midpoint, frame_path)
        with Image.open(frame_path) as raw_img:
            img = raw_img.convert("RGB").resize((168, 298))
        canvas = Image.new("RGB", (168, 326), "white")
        canvas.paste(img, (0, 0))
        label = f"S{scene_index}: {round(start_sec, 1)}-{round(end_sec, 1)}s"
        ImageDraw.Draw(canvas).text((8, 304), label, fill=(0, 0, 0))
        thumbs.append(canvas)
    if not thumbs:
        return ""
    cols = 4
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 168, rows * 326), (240, 240, 240))
    for idx, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((idx % cols) * 168, (idx // cols) * 326))
    sheet.save(output_path, quality=88)
    return output_path


def _image_diff_score(prev_path: str, next_path: str) -> Dict[str, float]:
    with Image.open(prev_path) as prev_img, Image.open(next_path) as next_img:
        prev = prev_img.convert("L")
        nxt = next_img.convert("L").resize(prev.size)
        diff = ImageChops.difference(prev, nxt)
        stat = ImageStat.Stat(diff)
        mean = float(stat.mean[0]) / 255.0
        center_crop = _center_crop(diff)
        center_mean = float(ImageStat.Stat(center_crop).mean[0]) / 255.0
        return {"full": mean, "center": center_mean}


def _histogram_similarity(prev_path: str, next_path: str) -> float:
    with Image.open(prev_path) as prev_img, Image.open(next_path) as next_img:
        prev = prev_img.convert("L").resize((64, 64))
        nxt = next_img.convert("L").resize((64, 64))
        hist_a = prev.histogram()
        hist_b = nxt.histogram()
        total_a = sum(hist_a) or 1
        total_b = sum(hist_b) or 1
        intersection = sum(min(a / total_a, b / total_b) for a, b in zip(hist_a, hist_b))
        return max(0.0, min(1.0, intersection))


def _center_crop(image: Image.Image) -> Image.Image:
    width, height = image.size
    left = int(width * 0.25)
    right = int(width * 0.75)
    top = int(height * 0.18)
    bottom = int(height * 0.85)
    return image.crop((left, top, right, bottom))


def _motion_metrics(frames: List[str], probe: Dict[str, Any], scene_metrics: Dict[str, Any]) -> Dict[str, Any]:
    diffs = [_image_diff_score(frames[i - 1], frames[i]) for i in range(1, len(frames))]
    full_scores = [item["full"] for item in diffs]
    center_scores = [item["center"] for item in diffs]
    avg_full = sum(full_scores) / len(full_scores) if full_scores else 0.0
    avg_center = sum(center_scores) / len(center_scores) if center_scores else 0.0
    visual_change_events = sum(1 for score in full_scores if score >= 0.075)
    camera_score = min(1.0, avg_full * 5.0)
    character_score = max(0.0, min(1.0, (avg_center - (avg_full * 0.45)) * 5.0))
    total_movement = min(1.0, math.sqrt(avg_full) * 1.6) if avg_full else 0.0
    scene_count = scene_metrics.get("scene_count", 1)
    scene_factor = min(1.0, max(0, scene_count - 1) / 5.0)
    camera_choreo_factor = 0.0
    if camera_score >= 0.65:
        camera_choreo_factor = 0.25
    if camera_score >= 0.85:
        camera_choreo_factor = 0.4
    recreation_basis = (
        scene_factor * 0.42
        + camera_choreo_factor
        + min(1.0, character_score) * 0.18
        + min(1.0, total_movement) * 0.12
    )
    motion_amount = _movement_label(total_movement)
    recreation_difficulty = _difficulty_label(recreation_basis)
    return {
        "duration_sec": probe.get("duration_sec", 0),
        "fps": probe.get("fps", 0),
        "estimated_total_frame_count": probe.get("estimated_total_frame_count", 0),
        "sampled_frame_count": len(frames),
        "scene_count": scene_count,
        "scene_change_count": scene_metrics.get("scene_change_count", 0),
        "scene_timeline": scene_metrics.get("scene_timeline", []),
        "first_scene_change_sec": scene_metrics.get("first_scene_change_sec"),
        "first_scene_change_frame": scene_metrics.get("first_scene_change_frame"),
        "first_scene_duration_sec": scene_metrics.get("first_scene_duration_sec"),
        "can_crop_to_first_scene": scene_metrics.get("can_crop_to_first_scene", False),
        "scene_detection_error": scene_metrics.get("scene_detection_error", ""),
        "first_two_scene_similarity_score": scene_metrics.get("first_two_scene_similarity_score"),
        "first_two_scene_structure_similarity_score": scene_metrics.get("first_two_scene_structure_similarity_score"),
        "first_two_scene_camera_similarity_score": scene_metrics.get("first_two_scene_camera_similarity_score"),
        "first_two_scene_character_similarity_score": scene_metrics.get("first_two_scene_character_similarity_score"),
        "first_two_scenes_similar": scene_metrics.get("first_two_scenes_similar"),
        "scene_similarity_pairs": scene_metrics.get("scene_similarity_pairs", []),
        "average_adjacent_scene_similarity_score": scene_metrics.get("average_adjacent_scene_similarity_score"),
        "lowest_adjacent_scene_similarity_score": scene_metrics.get("lowest_adjacent_scene_similarity_score"),
        "lowest_adjacent_scene_similarity_pair": scene_metrics.get("lowest_adjacent_scene_similarity_pair"),
        "scene_similarity_error": scene_metrics.get("scene_similarity_error", ""),
        "visual_change_events": visual_change_events,
        "total_frame_changes": visual_change_events,
        "total_frame_movement": round(total_movement, 4),
        "camera_movement_score": round(camera_score, 4),
        "character_movement_score": round(character_score, 4),
        "motion_amount": motion_amount,
        "recreation_difficulty_score": round(recreation_basis, 4),
        "recreation_difficulty": recreation_difficulty,
        "motion_difficulty": recreation_difficulty,
    }


def _difficulty_label(score: float) -> str:
    if score < 0.18:
        return "very_easy"
    if score < 0.34:
        return "easy"
    if score < 0.54:
        return "medium"
    if score < 0.74:
        return "hard"
    return "very_hard"


def _movement_label(score: float) -> str:
    if score < 0.18:
        return "very_low"
    if score < 0.34:
        return "low"
    if score < 0.54:
        return "medium"
    if score < 0.74:
        return "high"
    return "very_high"


def _representative_frames(frames: List[str], count: int = 4) -> List[str]:
    if len(frames) <= count:
        return frames
    indexes = sorted({round(i * (len(frames) - 1) / (count - 1)) for i in range(count)})
    return [frames[i] for i in indexes]


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _json_schema() -> Dict[str, Any]:
    return {
        "name": "video_recreation_tags",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "niche": {"type": "string", "enum": NICHE_VALUES},
                "sub_niche": {"type": "string"},
                "format": {"type": "string", "enum": FORMAT_VALUES},
                "hook_type": {"type": "string", "enum": HOOK_VALUES},
                "scene_type": {"type": "string", "enum": SCENE_VALUES},
                "camera_movement": {"type": "string", "enum": CAMERA_VALUES},
                "visual_pattern": {"type": "string", "enum": VISUAL_VALUES},
                "motion_amount": {"type": "string", "enum": MOVEMENT_AMOUNT_VALUES},
                "recreation_difficulty": {"type": "string", "enum": MOTION_DIFFICULTY_VALUES},
                "motion_difficulty": {"type": "string", "enum": MOTION_DIFFICULTY_VALUES},
                "content_pillar": {"type": "string", "enum": CONTENT_PILLAR_VALUES},
                "pillar_role": {"type": "string", "enum": PILLAR_ROLE_VALUES},
                "account_archetype": {"type": "string", "enum": ACCOUNT_ARCHETYPE_VALUES},
                "account_voice": {"type": "string", "enum": ACCOUNT_VOICE_VALUES},
                "audience_stage": {"type": "string", "enum": AUDIENCE_STAGE_VALUES},
                "audience_identity": {"type": "string", "enum": AUDIENCE_IDENTITY_VALUES},
                "funnel_stage": {"type": "string", "enum": FUNNEL_STAGE_VALUES},
                "campaign_use": {"type": "string", "enum": CAMPAIGN_USE_VALUES},
                "conversion_intent": {"type": "string", "enum": CONVERSION_INTENT_VALUES},
                "cta_type": {"type": "string", "enum": CTA_TYPE_VALUES},
                "product_integration_type": {"type": "string", "enum": PRODUCT_INTEGRATION_VALUES},
                "primary_product_name": {"type": "string"},
                "primary_product_type": {"type": "string", "enum": PRODUCT_TYPE_VALUES},
                "product_mention_type": {"type": "string", "enum": PRODUCT_MENTION_TYPE_VALUES},
                "product_mention_context": {"type": "string"},
                "mentioned_products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "name": {"type": "string"},
                            "product_type": {"type": "string", "enum": PRODUCT_TYPE_VALUES},
                            "mention_type": {"type": "string", "enum": PRODUCT_MENTION_TYPE_VALUES},
                            "context": {"type": "string"},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["name", "product_type", "mention_type", "context", "confidence"],
                    },
                },
                "product_visibility": {"type": "string", "enum": PRODUCT_VISIBILITY_VALUES},
                "product_fit": {"type": "string", "enum": PRODUCT_FIT_VALUES},
                "demo_depth": {"type": "string", "enum": DEMO_DEPTH_VALUES},
                "creative_template": {"type": "string", "enum": CREATIVE_TEMPLATE_VALUES},
                "script_structure": {"type": "string", "enum": SCRIPT_STRUCTURE_VALUES},
                "repeatability": {"type": "string", "enum": REPEATABILITY_VALUES},
                "production_complexity": {"type": "string", "enum": PRODUCTION_COMPLEXITY_VALUES},
                "location_complexity": {"type": "string", "enum": LOCATION_COMPLEXITY_VALUES},
                "asset_requirements": {
                    "type": "array",
                    "items": {"type": "string", "enum": ASSET_REQUIREMENT_VALUES},
                },
                "requires_voiceover": {"type": "string", "enum": TRI_STATE_VALUES},
                "requires_text_overlay": {"type": "string", "enum": TEXT_OVERLAY_VALUES},
                "requires_trend_audio": {"type": "string", "enum": TRI_STATE_VALUES},
                "cta_strength": {"type": "string", "enum": CTA_STRENGTH_VALUES},
                "detected_text_cues": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "scene_roles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "scene_index": {"type": "integer"},
                            "role": {"type": "string", "enum": SCENE_ROLE_VALUES},
                            "start_sec": {"type": "number"},
                            "end_sec": {"type": "number"},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "required": ["scene_index", "role", "start_sec", "end_sec", "confidence"],
                    },
                },
                "is_hook_then_demo": {"type": "boolean"},
                "hook_scene_count": {"type": "integer"},
                "demo_scene_count": {"type": "integer"},
                "cta_scene_count": {"type": "integer"},
                "demo_start_sec": {"type": "number"},
                "campaign_fit_score": {"type": "number", "minimum": 0, "maximum": 1},
                "account_fit_score": {"type": "number", "minimum": 0, "maximum": 1},
                "repeatability_score": {"type": "number", "minimum": 0, "maximum": 1},
                "viral_score": {"type": "number", "minimum": 0, "maximum": 1},
                "conversion_potential_score": {"type": "number", "minimum": 0, "maximum": 1},
                "trust_building_score": {"type": "number", "minimum": 0, "maximum": 1},
                "education_value_score": {"type": "number", "minimum": 0, "maximum": 1},
                "entertainment_value_score": {"type": "number", "minimum": 0, "maximum": 1},
                "production_ease_score": {"type": "number", "minimum": 0, "maximum": 1},
                "hook_summary": {"type": "string"},
                "first_three_seconds": {"type": "string"},
                "recreation_notes": {"type": "string"},
                "ai_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": [
                "niche", "sub_niche", "format", "hook_type", "scene_type", "camera_movement",
                "visual_pattern", "motion_amount", "recreation_difficulty", "motion_difficulty",
                "content_pillar", "pillar_role", "account_archetype", "account_voice",
                "audience_stage", "audience_identity",
                "funnel_stage", "campaign_use", "conversion_intent", "cta_type",
                "product_integration_type", "primary_product_name", "primary_product_type",
                "product_mention_type", "product_mention_context", "mentioned_products",
                "product_visibility", "product_fit", "demo_depth",
                "creative_template", "script_structure", "repeatability", "production_complexity",
                "location_complexity", "asset_requirements", "requires_voiceover",
                "requires_text_overlay", "requires_trend_audio", "cta_strength",
                "detected_text_cues", "scene_roles",
                "is_hook_then_demo", "hook_scene_count", "demo_scene_count",
                "cta_scene_count", "demo_start_sec", "campaign_fit_score",
                "account_fit_score", "repeatability_score", "viral_score",
                "conversion_potential_score", "trust_building_score", "education_value_score",
                "entertainment_value_score", "production_ease_score", "hook_summary",
                "first_three_seconds", "recreation_notes", "ai_confidence",
            ],
        },
        "strict": True,
    }


def _tag_with_openai(video_reference: Dict[str, Any], motion_metrics: Dict[str, Any], frames: List[str]) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise VideoAnalysisError("Missing OPENAI_API_KEY for structured video tagging.", 503)
    try:
        from openai import OpenAI
    except Exception as exc:
        raise VideoAnalysisError("OpenAI SDK is not installed in the backend environment.", 503) from exc

    frame_payload = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{_encode_image(path)}"},
        }
        for path in frames
    ]
    taxonomy_text = json.dumps({
        "sub_niches_by_niche": SUB_NICHE_VALUES,
        "formats": FORMAT_VALUES,
        "hook_types": HOOK_VALUES,
        "scene_roles": SCENE_ROLE_VALUES,
        "product_mention_types": PRODUCT_MENTION_TYPE_VALUES,
        "cta_strengths": CTA_STRENGTH_VALUES,
        "visual_patterns": VISUAL_VALUES,
        "content_pillars": CONTENT_PILLAR_VALUES,
        "account_archetypes": ACCOUNT_ARCHETYPE_VALUES,
        "campaign_uses": CAMPAIGN_USE_VALUES,
        "creative_templates": CREATIVE_TEMPLATE_VALUES,
        "script_structures": SCRIPT_STRUCTURE_VALUES,
    }, indent=2)
    content = [
        {
            "type": "text",
            "text": (
                "Tag this short-form video for cheap recreation. Use only fixed enum values. "
                "Also tag it for account strategy and campaign composition planning. "
                "Pick sub_niche from the group matching niche; use other if uncertain. "
                "Scores are 0 to 1. Use content_pillar as the primary account mix bucket.\n\n"
                "Important definitions:\n"
                "- talking_head means a person is visibly speaking or presenting to camera. Do not use it just because a face is visible.\n"
                "- before_after requires two distinct states, edits, or explicit transformation proof. Do not use it for a single physique, outfit, or product showcase.\n"
                "- bold_claim requires an explicit spoken, caption, or text claim. If the hook is mainly the visual, use visual_body_hook, visual_reveal, aesthetic_hook, or no_explicit_hook.\n"
                "- motion_amount is visible movement. recreation_difficulty is how hard the clip is to recreate for a campaign. A one-scene mirror/body clip can have medium/high visible movement but easy recreation.\n"
                "- Prefer visual_only or audio_only_visual when there is no evidence of a spoken script, tutorial, or story arc.\n"
                "- Use mirror_body_showcase/body_check/physique_showcase for physique, outfit, body check, flexing, or mirror pose clips that are primarily visual.\n\n"
                "Product mention rules:\n"
                "- Extract every visible, captioned, or spoken product/app/brand name into mentioned_products.\n"
                "- If a long text overlay includes an app or brand name, set primary_product_name to that name and product_mention_type to text_overlay.\n"
                "- A product can be mentioned without being demoed. In that case use product_integration_type mentioned_only, product_visibility low, demo_depth none, and cta_strength light if the wording nudges the viewer to use it.\n"
                "- Use cta_strength light for subtle mentions like 'use/try with [app name]' inside relatable text, medium/strong for direct 'download now', 'try free', 'link in bio', or explicit offer language.\n"
                "- detected_text_cues should include short exact or near-exact text snippets that explain the hook, CTA, product name, or audience pain point.\n\n"
                "Scene role rules:\n"
                "- If the first scene introduces a pain point, curiosity gap, promise, or reason to watch, label it hook.\n"
                "- If later scenes show the product/app/interface/process in use, label those scenes demo_step, not generic broll.\n"
                "- If a scene asks the viewer to download, try, buy, click, or use the app, label it cta.\n"
                "- If scene 1 is hook and most later scenes are demo_step/product_showcase, set format hook_demo, creative_template hook_then_demo, script_structure hook_then_demo, and is_hook_then_demo true.\n"
                "- A hook_demo can have many demo scenes. Use demo_start_sec for the start of the first demo/product scene.\n\n"
                f"Campaign taxonomy hints:\n{taxonomy_text}\n\n"
                f"Metadata:\n{json.dumps(_metadata_for_prompt(video_reference), indent=2)}\n\n"
                f"Local motion metrics:\n{json.dumps(motion_metrics, indent=2)}"
            ),
        },
        *frame_payload,
    ]
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_TAGGING_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise creative analyst for short-form ads. "
                    "Return compact recreation tags only."
                ),
            },
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_schema", "json_schema": _json_schema()},
        temperature=0.1,
    )
    raw_text = response.choices[0].message.content or "{}"
    try:
        tags = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise VideoAnalysisError("OpenAI returned invalid JSON tags.", 502) from exc
    return _normalize_tags(tags, motion_metrics)


def _metadata_for_prompt(video_reference: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "platform": video_reference.get("platform"),
        "creatorHandle": video_reference.get("creatorHandle"),
        "caption": video_reference.get("caption"),
        "hashtags": video_reference.get("hashtags") or [],
        "durationSec": video_reference.get("durationSec"),
        "metrics": video_reference.get("metrics") or {},
    }


def _normalize_tags(tags: Dict[str, Any], motion_metrics: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(tags)
    normalized["niche"] = normalized.get("niche") if normalized.get("niche") in NICHE_VALUES else "other"
    allowed_subs = SUB_NICHE_VALUES.get(normalized["niche"], ["other"])
    if normalized.get("sub_niche") not in allowed_subs:
        normalized["sub_niche"] = "other"
    for key, allowed in [
        ("format", FORMAT_VALUES),
        ("hook_type", HOOK_VALUES),
        ("scene_type", SCENE_VALUES),
        ("camera_movement", CAMERA_VALUES),
        ("visual_pattern", VISUAL_VALUES),
        ("motion_amount", MOVEMENT_AMOUNT_VALUES),
        ("recreation_difficulty", MOTION_DIFFICULTY_VALUES),
        ("motion_difficulty", MOTION_DIFFICULTY_VALUES),
        ("content_pillar", CONTENT_PILLAR_VALUES),
        ("pillar_role", PILLAR_ROLE_VALUES),
        ("account_archetype", ACCOUNT_ARCHETYPE_VALUES),
        ("account_voice", ACCOUNT_VOICE_VALUES),
        ("audience_stage", AUDIENCE_STAGE_VALUES),
        ("audience_identity", AUDIENCE_IDENTITY_VALUES),
        ("funnel_stage", FUNNEL_STAGE_VALUES),
        ("campaign_use", CAMPAIGN_USE_VALUES),
        ("conversion_intent", CONVERSION_INTENT_VALUES),
        ("cta_type", CTA_TYPE_VALUES),
        ("product_integration_type", PRODUCT_INTEGRATION_VALUES),
        ("primary_product_type", PRODUCT_TYPE_VALUES),
        ("product_mention_type", PRODUCT_MENTION_TYPE_VALUES),
        ("product_visibility", PRODUCT_VISIBILITY_VALUES),
        ("product_fit", PRODUCT_FIT_VALUES),
        ("demo_depth", DEMO_DEPTH_VALUES),
        ("creative_template", CREATIVE_TEMPLATE_VALUES),
        ("script_structure", SCRIPT_STRUCTURE_VALUES),
        ("repeatability", REPEATABILITY_VALUES),
        ("production_complexity", PRODUCTION_COMPLEXITY_VALUES),
        ("location_complexity", LOCATION_COMPLEXITY_VALUES),
        ("requires_voiceover", TRI_STATE_VALUES),
        ("requires_text_overlay", TEXT_OVERLAY_VALUES),
        ("requires_trend_audio", TRI_STATE_VALUES),
        ("cta_strength", CTA_STRENGTH_VALUES),
    ]:
        if normalized.get(key) not in allowed:
            normalized[key] = "other" if "other" in allowed else allowed[0]
    normalized["primary_product_name"] = str(normalized.get("primary_product_name") or "").strip()
    normalized["product_mention_context"] = str(normalized.get("product_mention_context") or "").strip()
    normalized["mentioned_products"] = _normalize_mentioned_products(normalized.get("mentioned_products"))
    normalized = _sync_product_mention_summary(normalized)
    text_cues = normalized.get("detected_text_cues")
    if not isinstance(text_cues, list):
        text_cues = []
    normalized["detected_text_cues"] = [str(item).strip()[:180] for item in text_cues if str(item).strip()][:8]
    requirements = normalized.get("asset_requirements")
    if not isinstance(requirements, list):
        requirements = []
    normalized["asset_requirements"] = [
        item for item in requirements
        if item in ASSET_REQUIREMENT_VALUES
    ]
    normalized["scene_roles"] = _normalize_scene_roles(normalized.get("scene_roles"), motion_metrics)
    normalized = _sync_scene_role_summary(normalized, motion_metrics)
    if motion_metrics.get("motion_amount") in MOVEMENT_AMOUNT_VALUES:
        normalized["motion_amount"] = motion_metrics["motion_amount"]
    if motion_metrics.get("recreation_difficulty") in MOTION_DIFFICULTY_VALUES:
        normalized["recreation_difficulty"] = motion_metrics["recreation_difficulty"]
        normalized["motion_difficulty"] = motion_metrics["recreation_difficulty"]
    normalized = _apply_tag_guardrails(normalized, motion_metrics)
    for score_field in SCORE_FIELDS:
        normalized[score_field] = max(0.0, min(1.0, _safe_float(normalized.get(score_field), 0.0)))
    normalized["ai_confidence"] = max(0.0, min(1.0, _safe_float(normalized.get("ai_confidence"), 0.0)))
    return normalized


def _sync_product_mention_summary(tags: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(tags)
    products = normalized.get("mentioned_products") if isinstance(normalized.get("mentioned_products"), list) else []
    primary = products[0] if products else {}
    if not normalized.get("primary_product_name") and primary:
        normalized["primary_product_name"] = primary.get("name", "")
    if normalized.get("primary_product_type") == "unknown" and primary:
        normalized["primary_product_type"] = primary.get("product_type", "unknown")
    if normalized.get("product_mention_type") == "none" and primary:
        normalized["product_mention_type"] = primary.get("mention_type", "none")
    if not normalized.get("product_mention_context") and primary:
        normalized["product_mention_context"] = primary.get("context", "")

    has_product_mention = bool(normalized.get("primary_product_name") or products)
    if has_product_mention and normalized.get("product_integration_type") == "none":
        normalized["product_integration_type"] = "mentioned_only"
    if has_product_mention and normalized.get("product_visibility") == "none":
        normalized["product_visibility"] = "low"
    if has_product_mention and normalized.get("product_fit") == "poor":
        normalized["product_fit"] = "native"
    if has_product_mention and normalized.get("conversion_intent") == "none" and normalized.get("cta_strength") in {"light", "medium"}:
        normalized["conversion_intent"] = "soft_sell"
    if has_product_mention and normalized.get("funnel_stage") == "awareness" and normalized.get("cta_strength") in {"medium", "strong"}:
        normalized["funnel_stage"] = "consideration"
    return normalized


def _normalize_mentioned_products(raw_products: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_products, list):
        return []
    normalized = []
    seen = set()
    for item in raw_products:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        product_type = item.get("product_type") if item.get("product_type") in PRODUCT_TYPE_VALUES else "unknown"
        mention_type = item.get("mention_type") if item.get("mention_type") in PRODUCT_MENTION_TYPE_VALUES else "none"
        normalized.append({
            "name": name[:80],
            "product_type": product_type,
            "mention_type": mention_type,
            "context": str(item.get("context") or "").strip()[:180],
            "confidence": max(0.0, min(1.0, _safe_float(item.get("confidence"), 0.5))),
        })
    return normalized[:8]


def _normalize_scene_roles(raw_roles: Any, motion_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    timeline = motion_metrics.get("scene_timeline") or []
    if not isinstance(timeline, list) or not timeline:
        return []
    timeline_by_index = {
        int(_safe_float(scene.get("scene_index"), idx + 1)): scene
        for idx, scene in enumerate(timeline)
        if isinstance(scene, dict)
    }
    input_roles = raw_roles if isinstance(raw_roles, list) else []
    role_by_index: Dict[int, Dict[str, Any]] = {}
    for item in input_roles:
        if not isinstance(item, dict):
            continue
        scene_index = int(_safe_float(item.get("scene_index"), 0))
        if scene_index not in timeline_by_index:
            continue
        role = item.get("role") if item.get("role") in SCENE_ROLE_VALUES else "other"
        role_by_index[scene_index] = {
            "scene_index": scene_index,
            "role": role,
            "confidence": max(0.0, min(1.0, _safe_float(item.get("confidence"), 0.5))),
        }

    normalized = []
    for scene_index, scene in sorted(timeline_by_index.items()):
        role_item = role_by_index.get(scene_index) or {
            "scene_index": scene_index,
            "role": "other",
            "confidence": 0.0,
        }
        normalized.append({
            "scene_index": scene_index,
            "role": role_item["role"],
            "start_sec": _safe_float(scene.get("start_sec"), 0.0),
            "end_sec": _safe_float(scene.get("end_sec"), 0.0),
            "confidence": role_item["confidence"],
        })
    return normalized


def _sync_scene_role_summary(tags: Dict[str, Any], motion_metrics: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(tags)
    roles = normalized.get("scene_roles") if isinstance(normalized.get("scene_roles"), list) else []
    hook_roles = [role for role in roles if role.get("role") == "hook"]
    demo_roles = [role for role in roles if role.get("role") in {"demo_step", "product_showcase"}]
    cta_roles = [role for role in roles if role.get("role") == "cta"]
    normalized["hook_scene_count"] = len(hook_roles)
    normalized["demo_scene_count"] = len(demo_roles)
    normalized["cta_scene_count"] = len(cta_roles)
    normalized["demo_start_sec"] = min([_safe_float(role.get("start_sec")) for role in demo_roles], default=0.0)
    normalized["is_hook_then_demo"] = bool(
        roles
        and roles[0].get("role") == "hook"
        and len(demo_roles) >= 1
        and normalized["demo_start_sec"] >= _safe_float(roles[0].get("end_sec"), 0.0) - 0.15
    )

    if normalized["is_hook_then_demo"]:
        normalized["format"] = "hook_demo"
        normalized["creative_template"] = "hook_then_demo"
        normalized["script_structure"] = "hook_then_demo"
        if normalized.get("product_integration_type") in {"none", "background_context", "mentioned_only"}:
            normalized["product_integration_type"] = "demo_core"
        if normalized.get("demo_depth") in {"none", "feature_flash"}:
            normalized["demo_depth"] = "multi_step_walkthrough" if len(demo_roles) > 1 else "single_feature_walkthrough"
        if normalized.get("product_visibility") in {"none", "low"}:
            normalized["product_visibility"] = "high"
        if normalized.get("cta_type") in {"download_app", "try_free", "shop_now", "link_in_bio"}:
            normalized["funnel_stage"] = "conversion"
            normalized["conversion_intent"] = "hard_sell"
        elif normalized.get("product_integration_type") == "demo_core":
            normalized["funnel_stage"] = "consideration"
            normalized["conversion_intent"] = "medium_sell"

    if (
        "app_screen" in (normalized.get("asset_requirements") or [])
        and normalized.get("product_integration_type") == "demo_core"
        and normalized.get("funnel_stage") == "conversion"
        and normalized.get("cta_type") in {"no_cta", "link_in_bio"}
    ):
        normalized["cta_type"] = "download_app"

    if cta_roles and normalized.get("cta_type") in {"download_app", "try_free", "shop_now"}:
        normalized["funnel_stage"] = "conversion"
        normalized["conversion_intent"] = "hard_sell"
    return normalized


def _apply_tag_guardrails(tags: Dict[str, Any], motion_metrics: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(tags)
    scene_count = int(_safe_float(motion_metrics.get("scene_count"), 1))
    scene_change_count = int(_safe_float(motion_metrics.get("scene_change_count"), 0))
    static_or_light_camera = normalized.get("camera_movement") in {"static", "handheld_light"}
    visual_only = normalized.get("script_structure") in {"visual_only", "audio_only_visual", "text_overlay_only"}
    mirror_or_body = (
        normalized.get("scene_type") == "bathroom_mirror"
        or normalized.get("visual_pattern") in {"mirror_shot", "body_focus", "pose_sequence", "outfit_check"}
        or "body" in (normalized.get("asset_requirements") or [])
    )

    if normalized.get("format") == "talking_head" and visual_only:
        normalized["format"] = "mirror_body_showcase" if mirror_or_body else "visual_showcase"

    if mirror_or_body and visual_only:
        if normalized.get("format") in {"talking_head", "hook_demo", "other"}:
            normalized["format"] = "mirror_body_showcase"
        if normalized.get("visual_pattern") == "face_to_camera":
            normalized["visual_pattern"] = "mirror_shot" if normalized.get("scene_type") == "bathroom_mirror" else "body_focus"
        if normalized.get("creative_template") in {"before_after", "hook_then_demo", "problem_then_solution"}:
            normalized["creative_template"] = "body_check"
        if normalized.get("hook_type") in {"bold_claim", "problem_callout", "relatable_story", "question"}:
            normalized["hook_type"] = "visual_body_hook"
        normalized["requires_voiceover"] = "no"

    if normalized.get("creative_template") == "before_after" and scene_count <= 1:
        normalized["creative_template"] = "comparison_reveal" if normalized.get("format") == "comparison" else "visual_showcase"
    if normalized.get("hook_type") == "before_after" and scene_count <= 1:
        normalized["hook_type"] = "visual_reveal" if mirror_or_body else "no_explicit_hook"

    if normalized.get("hook_type") == "bold_claim" and visual_only and normalized.get("requires_text_overlay") == "none":
        normalized["hook_type"] = "visual_body_hook" if mirror_or_body else "aesthetic_hook"

    if scene_count <= 1 and static_or_light_camera and normalized.get("production_complexity") == "high":
        normalized["production_complexity"] = "low" if visual_only else "medium"

    if scene_count <= 1 and scene_change_count == 0 and static_or_light_camera and visual_only:
        normalized["recreation_difficulty"] = _easier_label(normalized.get("recreation_difficulty"), ceiling="easy")
        normalized["motion_difficulty"] = normalized["recreation_difficulty"]
        normalized["production_ease_score"] = max(_safe_float(normalized.get("production_ease_score"), 0.0), 0.75)
        if normalized.get("repeatability") == "one_off":
            normalized["repeatability"] = "template_reusable"
        normalized["repeatability_score"] = max(_safe_float(normalized.get("repeatability_score"), 0.0), 0.7)

    return normalized


def _easier_label(value: Any, ceiling: str = "medium") -> str:
    order = ["very_easy", "easy", "medium", "hard", "very_hard"]
    current = value if value in order else "medium"
    return order[min(order.index(current), order.index(ceiling))]


def analyze_video_reference(video_reference: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dirs()
    analysis_id = f"analysis_{uuid.uuid4().hex[:12]}"
    work_dir = os.path.join(VIDEO_ANALYSIS_TEMP_DIR, analysis_id)
    frame_dir = os.path.join(VIDEO_ANALYSIS_FRAME_DIR, analysis_id)
    os.makedirs(work_dir, exist_ok=True)
    video_path = os.path.join(work_dir, "source_video")
    frame_paths: List[str] = []

    try:
        download = _download_video(video_reference, video_path)
        downloaded_path = download["path"]
        probe = _ffprobe(downloaded_path)
        scene_metrics = _scene_metrics(downloaded_path)
        frame_paths = _sample_frames(downloaded_path, frame_dir)
        motion_metrics = _motion_metrics(frame_paths, probe, scene_metrics)
        selected_frames = _representative_frames(frame_paths, 4)
        scene_contact_sheet = _scene_role_contact_sheet(
            downloaded_path,
            scene_metrics.get("scene_timeline", []),
            os.path.join(work_dir, "scene_roles.jpg"),
        )
        if scene_contact_sheet:
            selected_frames.append(scene_contact_sheet)
        normalized_tags = _tag_with_openai(video_reference, motion_metrics, selected_frames)
        kept_frames = frame_paths if VIDEO_ANALYSIS_KEEP_FRAMES else []
        return {
            "analysisId": analysis_id,
            "status": "tagged",
            "normalizedTags": normalized_tags,
            "motionMetrics": motion_metrics,
            "sampledFrames": kept_frames,
            "rawAiOutput": normalized_tags,
            "downloadedBytes": download["downloadedBytes"],
            "downloadMethod": download["method"],
            "sourceVideoDeleted": True,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if not VIDEO_ANALYSIS_KEEP_FRAMES:
            shutil.rmtree(frame_dir, ignore_errors=True)
