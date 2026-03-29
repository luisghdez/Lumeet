"""
Remix Service
=============
Orchestrates the remix pipeline:

    1. Download hook video from GCS
    2. (Optional) Apply caption overlay
    3. (Optional) Concatenate with extension video
    4. (Optional) Replace audio with selected sound
    5. Upload final remix to GCS

Reuses existing FFmpeg-based services:
    - caption_overlay.py
    - video_concatenator.py
    - audio_replacer.py
"""

from __future__ import annotations

import os
import logging
import requests
import tempfile
from typing import Optional

from caption_overlay import overlay_caption
from video_concatenator import concatenate_videos
from audio_replacer import replace_audio
from hook_metadata_store import hook_metadata_store
from sound_metadata_store import sound_metadata_store

logger = logging.getLogger("lumeet.remix_service")


class RemixError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _download_file(url: str, dest: str) -> str:
    """Download a file from a URL to a local path."""
    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return dest


def run_remix(
    hook_id: str,
    output_dir: str,
    caption: Optional[str] = None,
    sound_id: Optional[str] = None,
    extension_video_path: Optional[str] = None,
    on_step: Optional[callable] = None,
) -> dict:
    """
    Run the remix pipeline on a saved hook video.

    Args:
        hook_id: ID of the hook video to remix.
        output_dir: Directory for intermediate and final output files.
        caption: Optional caption text to overlay.
        sound_id: Optional sound ID to use for audio. If None and the hook
                  has an originalSoundId, that is used. Pass "__none__" to
                  skip audio replacement entirely.
        extension_video_path: Optional local path to a video to concatenate.
        on_step: Optional callback ``(step_key, event, message)``

    Returns:
        Dict with output paths and metadata.

    Raises:
        RemixError: If the hook or sound is not found.
    """
    cb = on_step or (lambda *a: None)
    os.makedirs(output_dir, exist_ok=True)

    result = {}

    # ---- Resolve hook ----
    hook = hook_metadata_store.get(hook_id)
    if not hook:
        raise RemixError(404, f"Hook {hook_id} not found.")
    hook_url = hook.get("url", "")
    if not hook_url:
        raise RemixError(500, f"Hook {hook_id} has no URL.")

    # ---- Resolve sound ----
    skip_audio = sound_id == "__none__"
    resolved_sound_id = sound_id
    if not resolved_sound_id and not skip_audio:
        resolved_sound_id = hook.get("originalSoundId")
    sound_url: Optional[str] = None
    if resolved_sound_id and not skip_audio:
        sound = sound_metadata_store.get(resolved_sound_id)
        if not sound:
            raise RemixError(404, f"Sound {resolved_sound_id} not found.")
        sound_url = sound.get("url", "")
        if not sound_url:
            raise RemixError(500, f"Sound {resolved_sound_id} has no URL.")

    # ---- Step 1: Download hook video ----
    cb("download_hook", "start", "Downloading hook video...")
    hook_local = os.path.join(output_dir, "hook_raw.mp4")
    try:
        _download_file(hook_url, hook_local)
    except Exception as exc:
        cb("download_hook", "fail", str(exc))
        raise RemixError(500, f"Failed to download hook video: {exc}")
    result["hook_video"] = hook_local
    cb("download_hook", "complete", "Hook video downloaded")

    working_video = hook_local

    # ---- Step 2: Caption overlay (optional) ----
    if caption and caption.strip():
        cb("caption_overlay", "start", "Applying caption overlay...")
        captioned_path = os.path.join(output_dir, "captioned.mp4")
        try:
            working_video = overlay_caption(
                working_video,
                caption.strip(),
                output_path=captioned_path,
            )
            result["captioned_video"] = working_video
        except Exception as exc:
            cb("caption_overlay", "fail", str(exc))
            raise RemixError(500, f"Caption overlay failed: {exc}")
        cb("caption_overlay", "complete", "Caption applied")

    # ---- Step 3: Concatenate extension video (optional) ----
    if extension_video_path and os.path.isfile(extension_video_path):
        cb("video_concatenation", "start", "Concatenating extension video...")
        concat_path = os.path.join(output_dir, "concatenated.mp4")
        try:
            working_video = concatenate_videos(
                working_video,
                extension_video_path,
                output_path=concat_path,
            )
            result["concatenated_video"] = working_video
        except Exception as exc:
            cb("video_concatenation", "fail", str(exc))
            raise RemixError(500, f"Video concatenation failed: {exc}")
        cb("video_concatenation", "complete", "Videos concatenated")

    # ---- Step 4: Audio replacement (optional) ----
    if sound_url and not skip_audio:
        cb("audio_replacement", "start", "Replacing audio...")
        sound_local = os.path.join(output_dir, "sound.aac")
        try:
            _download_file(sound_url, sound_local)
        except Exception as exc:
            cb("audio_replacement", "fail", f"Sound download failed: {exc}")
            raise RemixError(500, f"Failed to download sound: {exc}")

        final_path = os.path.join(output_dir, "remix_final.mp4")
        try:
            working_video = replace_audio(
                working_video,
                sound_local,
                output_path=final_path,
            )
            result["final_video"] = working_video
        except Exception as exc:
            cb("audio_replacement", "fail", str(exc))
            raise RemixError(500, f"Audio replacement failed: {exc}")
        cb("audio_replacement", "complete", "Audio replaced")
    else:
        result["final_video"] = working_video

    return result
