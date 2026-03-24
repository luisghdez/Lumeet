"""
Carousel orchestration service:
- Generate slides from prompt
- Upload to GCS
- Generate caption + hashtags
- Suggest a scheduling slot
- Persist metadata for retrieval
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from openai import OpenAI

from carousel_generator import (
    DEFAULT_HOOK_STYLE,
    _extract_response_text,
    _resolve_openai_api_key,
    _responses_with_model_fallback,
    generate_carousel,
)
from carousel_metadata_store import carousel_metadata_store
from config import CAROUSEL_SUGGESTION_MINUTES_STEP, GCS_OBJECT_PREFIX
from storage_gcs import GcsStorage, GcsStorageError


class CarouselServiceError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class CarouselService:
    def __init__(self):
        self.gcs = None

    def _gcs_or_error(self) -> GcsStorage:
        if self.gcs is not None:
            return self.gcs
        try:
            self.gcs = GcsStorage()
        except GcsStorageError as exc:
            raise CarouselServiceError(exc.status_code, exc.message) from exc
        except Exception as exc:
            raise CarouselServiceError(500, f"Failed to initialize GCS client: {exc}") from exc
        return self.gcs

    @staticmethod
    def _ordered_local_images(generated: Dict[str, Any]) -> List[Dict[str, Any]]:
        ordered: List[Dict[str, Any]] = []
        if generated.get("hook_path"):
            ordered.append(
                {
                    "kind": "hook",
                    "filename": os.path.basename(generated["hook_path"]),
                    "localPath": generated["hook_path"],
                }
            )
        for slide in generated.get("slides", []):
            path = slide.get("image_path")
            if not path:
                continue
            ordered.append(
                {
                    "kind": f"slide_{slide.get('number')}",
                    "filename": os.path.basename(path),
                    "localPath": path,
                    "number": slide.get("number"),
                    "tipTitle": slide.get("tip_title", ""),
                }
            )
        if generated.get("cta_path"):
            ordered.append(
                {
                    "kind": "cta",
                    "filename": os.path.basename(generated["cta_path"]),
                    "localPath": generated["cta_path"],
                }
            )
        return ordered

    @staticmethod
    def _next_slot_iso(timezone_name: str) -> str:
        step = max(5, CAROUSEL_SUGGESTION_MINUTES_STEP)
        now_local = datetime.now(ZoneInfo(timezone_name))
        # Suggest a near-future slot: add one step, then snap to that step.
        candidate = now_local + timedelta(minutes=step)
        floored = (candidate.minute // step) * step
        candidate = candidate.replace(minute=floored, second=0, microsecond=0)
        return candidate.isoformat()

    @staticmethod
    def _fallback_caption(prompt: str, slide_titles: List[str]) -> Dict[str, Any]:
        base = f"{prompt.strip()}\n\n" if prompt.strip() else ""
        highlights = " | ".join([t for t in slide_titles if t][:5])
        hashtags = ["#StudyTips", "#Learning", "#Productivity", "#Lumeet", "#Growth"]
        caption = f"{base}Swipe through for actionable takeaways.\n{highlights}\n\n{' '.join(hashtags)}".strip()
        return {"caption": caption[:2200], "hashtags": hashtags}

    def _generate_caption(self, prompt: str, slide_titles: List[str], api_key: str) -> Dict[str, Any]:
        client = OpenAI(api_key=api_key)
        system_prompt = (
            "Write high-converting social captions for carousel posts. "
            "Return JSON only with keys caption and hashtags."
        )
        user_prompt = (
            f"Prompt: {prompt}\n"
            f"Slide titles: {slide_titles}\n"
            "Requirements:\n"
            "- caption: max 700 chars, concise and engaging\n"
            "- hashtags: 5 to 10, each starts with #\n"
            '- Return strict JSON: {"caption":"...", "hashtags":["#a","#b"]}'
        )

        try:
            resp = _responses_with_model_fallback(
                client=client,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            text = _extract_response_text(resp).strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL).strip()
            parsed = json.loads(text)
            caption = str(parsed.get("caption", "")).strip()
            hashtags = [str(h).strip() for h in parsed.get("hashtags", []) if str(h).strip()]
            if not caption or not hashtags:
                return self._fallback_caption(prompt, slide_titles)
            normalized = [h if h.startswith("#") else f"#{h}" for h in hashtags]
            return {"caption": caption[:2200], "hashtags": normalized[:10]}
        except Exception:
            return self._fallback_caption(prompt, slide_titles)

    def create_carousel(self, *, prompt: str, timezone_name: str, hook_style: str = DEFAULT_HOOK_STYLE) -> Dict[str, Any]:
        if not prompt or not prompt.strip():
            raise CarouselServiceError(400, "prompt is required.")
        if not timezone_name:
            timezone_name = "UTC"
        try:
            ZoneInfo(timezone_name)
        except Exception as exc:
            raise CarouselServiceError(400, "Invalid timezone.") from exc

        api_key = _resolve_openai_api_key(None)
        if not api_key:
            raise CarouselServiceError(500, "OPENAI_API_KEY is required to generate carousel and caption.")

        carousel_id = uuid.uuid4().hex[:12]
        try:
            generated = generate_carousel(initial_prompt=prompt.strip(), hook_style=hook_style)
        except Exception as exc:
            raise CarouselServiceError(500, f"Carousel generation failed: {exc}") from exc

        ordered = self._ordered_local_images(generated)
        if not ordered:
            raise CarouselServiceError(500, "Carousel generation did not produce any images.")

        gcs = self._gcs_or_error()
        uploaded: List[Dict[str, Any]] = []
        for item in ordered:
            object_name = f"{GCS_OBJECT_PREFIX.strip('/')}/{carousel_id}/{item['filename']}"
            try:
                gcs_info = gcs.upload_file(item["localPath"], object_name)
            except Exception as exc:
                raise CarouselServiceError(500, f"Failed uploading image to GCS: {exc}") from exc

            uploaded.append(
                {
                    "kind": item["kind"],
                    "number": item.get("number"),
                    "tipTitle": item.get("tipTitle"),
                    "url": gcs_info["url"],
                    "bucket": gcs_info["bucket"],
                    "object": gcs_info["object"],
                }
            )

        slide_titles = [u.get("tipTitle") for u in uploaded if u.get("tipTitle")]
        caption_data = self._generate_caption(prompt=prompt, slide_titles=slide_titles, api_key=api_key)

        suggested = self._next_slot_iso(timezone_name)
        result = {
            "carouselId": carousel_id,
            "prompt": prompt.strip(),
            "status": "ready",
            "timezone": timezone_name,
            "suggestedScheduledFor": suggested,
            "captionDraft": caption_data["caption"],
            "hashtags": caption_data["hashtags"],
            "slides": uploaded,
            "mediaUrls": [u["url"] for u in uploaded],
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "outputDir": generated.get("output_dir"),
        }
        carousel_metadata_store.save(carousel_id, result)
        return result

    def _with_fresh_media_urls(self, item: Dict[str, Any]) -> Dict[str, Any]:
        slides = item.get("slides", []) or []
        refreshed_slides: List[Dict[str, Any]] = []
        gcs = None

        for slide in slides:
            updated = dict(slide)
            bucket = updated.get("bucket")
            object_name = updated.get("object")
            if bucket and object_name:
                # Lazily initialize only when needed.
                if gcs is None:
                    try:
                        gcs = self._gcs_or_error()
                    except CarouselServiceError:
                        gcs = None
                if gcs is not None and bucket == gcs.bucket_name:
                    updated["url"] = gcs.generate_read_url(object_name)
            refreshed_slides.append(updated)

        refreshed_item = dict(item)
        refreshed_item["slides"] = refreshed_slides
        refreshed_item["mediaUrls"] = [s.get("url") for s in refreshed_slides if s.get("url")]
        return refreshed_item

    def get_carousel(self, carousel_id: str) -> Dict[str, Any]:
        item = carousel_metadata_store.get(carousel_id)
        if not item:
            raise CarouselServiceError(404, f"Carousel {carousel_id} not found.")
        return self._with_fresh_media_urls(item)

    def list_carousels(self) -> Dict[str, Any]:
        items = [self._with_fresh_media_urls(item) for item in carousel_metadata_store.list_all()]
        return {"carousels": items}


carousel_service = CarouselService()
