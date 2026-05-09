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
import shutil
import subprocess
import uuid
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageStat

from config import (
    OPENAI_API_KEY,
    OPENAI_TAGGING_MODEL,
    VIDEO_ANALYSIS_DOWNLOAD_TIMEOUT_SEC,
    VIDEO_ANALYSIS_FRAME_DIR,
    VIDEO_ANALYSIS_FRAME_WIDTH,
    VIDEO_ANALYSIS_KEEP_FRAMES,
    VIDEO_ANALYSIS_MAX_DOWNLOAD_MB,
    VIDEO_ANALYSIS_MAX_FRAMES,
    VIDEO_ANALYSIS_SAMPLE_FPS,
    VIDEO_ANALYSIS_TEMP_DIR,
)


class VideoAnalysisError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


FORMAT_VALUES = ["ugc_demo", "talking_head", "storytime", "problem_solution", "hook_demo", "get_ready_with_me", "other"]
HOOK_VALUES = ["curiosity_gap", "problem_callout", "bold_claim", "social_proof", "demo_first", "before_after", "relatable_story", "question", "other"]
SCENE_VALUES = ["single_room", "bathroom_mirror", "bedroom", "desk_setup", "kitchen", "car", "outdoor", "screen_recording", "multi_scene", "other"]
CAMERA_VALUES = ["static", "handheld_light", "handheld_heavy", "push_in", "pull_back", "pan", "tilt", "walking_follow", "mixed"]
VISUAL_VALUES = ["face_to_camera", "product_in_hand", "product_closeup", "demo_steps", "text_overlay_heavy", "broll_montage", "mirror_shot", "screen_plus_face", "other"]
MOTION_DIFFICULTY_VALUES = ["very_easy", "easy", "medium", "hard", "very_hard"]
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
    "behind_the_scenes", "other",
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
]
SCRIPT_STRUCTURE_VALUES = [
    "hook_context_payoff", "problem_agitation_solution", "listicle", "story_arc",
    "demo_steps", "visual_only", "question_answer",
]
REPEATABILITY_VALUES = ["one_off", "repeatable_series", "template_reusable", "trend_dependent"]
PRODUCTION_COMPLEXITY_VALUES = ["low", "medium", "high"]
LOCATION_COMPLEXITY_VALUES = ["single_location", "multi_location", "public_location", "studio_like"]
ASSET_REQUIREMENT_VALUES = ["face", "body", "product", "app_screen", "food", "gym", "desk", "car", "outdoor"]
TRI_STATE_VALUES = ["yes", "no", "optional"]
TEXT_OVERLAY_VALUES = ["none", "light", "heavy"]
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


def _download_video(url: str, output_path: str) -> Dict[str, Any]:
    try:
        downloaded_bytes = _download_direct(url, output_path)
        return {"path": output_path, "downloadedBytes": downloaded_bytes, "method": "direct"}
    except VideoAnalysisError as exc:
        if "returned HTML" not in exc.message and "download failed" not in exc.message.lower():
            raise
        return _download_with_ytdlp(url, output_path)


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
        raise VideoAnalysisError(f"yt-dlp could not resolve/download this TikTok URL: {exc}", 422) from exc

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
    return {"path": filepath, "downloadedBytes": size, "method": "yt_dlp"}


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
        "first_scene_change_sec": round(first_change_sec, 3),
        "first_scene_change_frame": first_scene_end.get_frames(),
        "first_scene_duration_sec": round(first_change_sec - first_scene_start.get_seconds(), 3),
        "can_crop_to_first_scene": True,
        **_adjacent_scene_similarity(video_path, scene_list),
        "scene_detection_error": "",
    }


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
    difficulty_basis = (total_movement * 0.45) + (camera_score * 0.25) + (character_score * 0.30)
    return {
        "duration_sec": probe.get("duration_sec", 0),
        "fps": probe.get("fps", 0),
        "estimated_total_frame_count": probe.get("estimated_total_frame_count", 0),
        "sampled_frame_count": len(frames),
        "scene_count": scene_metrics.get("scene_count", 1),
        "scene_change_count": scene_metrics.get("scene_change_count", 0),
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
        "motion_difficulty": _difficulty_label(difficulty_basis),
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
                "visual_pattern", "motion_difficulty", "content_pillar", "pillar_role",
                "account_archetype", "account_voice", "audience_stage", "audience_identity",
                "funnel_stage", "campaign_use", "conversion_intent", "cta_type",
                "product_integration_type", "product_visibility", "product_fit", "demo_depth",
                "creative_template", "script_structure", "repeatability", "production_complexity",
                "location_complexity", "asset_requirements", "requires_voiceover",
                "requires_text_overlay", "requires_trend_audio", "campaign_fit_score",
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
        "content_pillars": CONTENT_PILLAR_VALUES,
        "account_archetypes": ACCOUNT_ARCHETYPE_VALUES,
        "campaign_uses": CAMPAIGN_USE_VALUES,
        "creative_templates": CREATIVE_TEMPLATE_VALUES,
    }, indent=2)
    content = [
        {
            "type": "text",
            "text": (
                "Tag this short-form video for cheap recreation. Use only fixed enum values. "
                "Also tag it for account strategy and campaign composition planning. "
                "Pick sub_niche from the group matching niche; use other if uncertain. "
                "Scores are 0 to 1. Use content_pillar as the primary account mix bucket.\n\n"
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
    ]:
        if normalized.get(key) not in allowed:
            normalized[key] = "other" if "other" in allowed else allowed[0]
    requirements = normalized.get("asset_requirements")
    if not isinstance(requirements, list):
        requirements = []
    normalized["asset_requirements"] = [
        item for item in requirements
        if item in ASSET_REQUIREMENT_VALUES
    ]
    if motion_metrics.get("motion_difficulty") in MOTION_DIFFICULTY_VALUES:
        normalized["motion_difficulty"] = motion_metrics["motion_difficulty"]
    for score_field in SCORE_FIELDS:
        normalized[score_field] = max(0.0, min(1.0, _safe_float(normalized.get(score_field), 0.0)))
    normalized["ai_confidence"] = max(0.0, min(1.0, _safe_float(normalized.get("ai_confidence"), 0.0)))
    return normalized


def analyze_video_reference(video_reference: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dirs()
    analysis_id = f"analysis_{uuid.uuid4().hex[:12]}"
    work_dir = os.path.join(VIDEO_ANALYSIS_TEMP_DIR, analysis_id)
    frame_dir = os.path.join(VIDEO_ANALYSIS_FRAME_DIR, analysis_id)
    os.makedirs(work_dir, exist_ok=True)
    video_path = os.path.join(work_dir, "source_video")
    frame_paths: List[str] = []

    try:
        download = _download_video(_source_url(video_reference), video_path)
        downloaded_path = download["path"]
        probe = _ffprobe(downloaded_path)
        scene_metrics = _scene_metrics(downloaded_path)
        frame_paths = _sample_frames(downloaded_path, frame_dir)
        motion_metrics = _motion_metrics(frame_paths, probe, scene_metrics)
        selected_frames = _representative_frames(frame_paths, 4)
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
