#!/usr/bin/env python3
"""
One-time backfill script
========================
Scans existing job folders for ``generated_raw.mp4`` and ``extracted_audio.aac``,
uploads them to GCS, and persists metadata in hook / sound stores.

Usage:
    cd backend && source venv/bin/activate
    python backfill_hooks_and_sounds.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone

# Ensure backend modules are importable
sys.path.insert(0, os.path.dirname(__file__))

from config import GCS_HOOKS_OBJECT_PREFIX, GCS_SOUNDS_OBJECT_PREFIX
from hook_metadata_store import hook_metadata_store
from sound_metadata_store import sound_metadata_store
from storage_gcs import GcsStorage


JOBS_DIR = os.path.join(os.path.dirname(__file__), "jobs")


def _get_audio_duration(audio_path: str) -> float:
    """Return audio duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return 0.0
    try:
        return float(result.stdout.strip())
    except (ValueError, TypeError):
        return 0.0


def backfill() -> None:
    gcs = GcsStorage()
    now_iso = datetime.now(timezone.utc).isoformat()

    job_dirs = sorted(
        d for d in os.listdir(JOBS_DIR)
        if os.path.isdir(os.path.join(JOBS_DIR, d))
    )

    hooks_uploaded = 0
    sounds_uploaded = 0

    # ---- Pass 1: upload hooks ----
    for job_id in job_dirs:
        raw_path = os.path.join(JOBS_DIR, job_id, "output", "generated_raw.mp4")
        if not os.path.isfile(raw_path):
            continue

        # Skip if already in store
        existing = hook_metadata_store.get(job_id)
        if existing:
            print(f"  [skip] Hook {job_id} already in store")
            continue

        object_name = f"{GCS_HOOKS_OBJECT_PREFIX.strip('/')}/{job_id}/raw.mp4"
        print(f"  Uploading hook {job_id} ...")
        try:
            gcs_info = gcs.upload_file_public(raw_path, object_name)
        except Exception as exc:
            print(f"  [error] GCS upload failed for hook {job_id}: {exc}")
            continue

        hook_metadata_store.save(job_id, {
            "hookId": job_id,
            "sourceJobId": job_id,
            "url": gcs_info.get("url", ""),
            "bucket": gcs_info.get("bucket", ""),
            "object": gcs_info.get("object", ""),
            "originalSoundId": None,  # patched in pass 3
            "label": "",
            "createdAt": now_iso,
        })
        hooks_uploaded += 1
        print(f"  [ok] Hook {job_id} uploaded")

    # ---- Pass 2: upload sounds ----
    for job_id in job_dirs:
        audio_path = os.path.join(JOBS_DIR, job_id, "output", "extracted_audio.aac")

        # If no extracted audio exists, try to extract from the reference video
        if not os.path.isfile(audio_path):
            # Look for a reference video in the input dir
            input_dir = os.path.join(JOBS_DIR, job_id, "input")
            ref_video = None
            for fname in ("reference_video.mp4", "reference_video.mov", "reference_video.avi"):
                candidate = os.path.join(input_dir, fname)
                if os.path.isfile(candidate):
                    ref_video = candidate
                    break
            # Also check the trimmed video from the output
            if not ref_video:
                trimmed = os.path.join(JOBS_DIR, job_id, "output", "trimmed.mp4")
                if os.path.isfile(trimmed):
                    ref_video = trimmed

            if ref_video:
                print(f"  Extracting audio from {os.path.basename(ref_video)} for {job_id} ...")
                try:
                    from audio_extractor import extract_audio
                    audio_path = os.path.join(JOBS_DIR, job_id, "output", "extracted_audio.aac")
                    extract_audio(ref_video, output_path=audio_path)
                except Exception as exc:
                    print(f"  [warn] Audio extraction failed for {job_id}: {exc}")
                    continue

        if not os.path.isfile(audio_path):
            continue

        sound_id = f"snd_{job_id}"

        # Skip if already in store
        existing = sound_metadata_store.get(sound_id)
        if existing:
            print(f"  [skip] Sound {sound_id} already in store")
            continue

        object_name = f"{GCS_SOUNDS_OBJECT_PREFIX.strip('/')}/{sound_id}/audio.aac"
        print(f"  Uploading sound {sound_id} ...")
        try:
            gcs_info = gcs.upload_file_public(audio_path, object_name)
        except Exception as exc:
            print(f"  [error] GCS upload failed for sound {sound_id}: {exc}")
            continue

        duration = _get_audio_duration(audio_path)

        sound_metadata_store.save(sound_id, {
            "soundId": sound_id,
            "sourceJobId": job_id,
            "sourceHookId": job_id,
            "url": gcs_info.get("url", ""),
            "bucket": gcs_info.get("bucket", ""),
            "object": gcs_info.get("object", ""),
            "label": "",
            "durationSec": round(duration, 2),
            "createdAt": now_iso,
        })
        sounds_uploaded += 1
        print(f"  [ok] Sound {sound_id} uploaded ({duration:.1f}s)")

    # ---- Pass 3: back-patch hooks with their original sound IDs ----
    for job_id in job_dirs:
        sound_id = f"snd_{job_id}"
        sound = sound_metadata_store.get(sound_id)
        if not sound:
            continue
        hook = hook_metadata_store.get(job_id)
        if not hook:
            continue
        if hook.get("originalSoundId") == sound_id:
            continue
        hook_metadata_store.update(job_id, originalSoundId=sound_id)
        print(f"  [link] Hook {job_id} -> Sound {sound_id}")

    print()
    print(f"Done! Uploaded {hooks_uploaded} hooks and {sounds_uploaded} sounds.")


if __name__ == "__main__":
    print("=" * 60)
    print("Backfill Hooks & Sounds to GCS")
    print("=" * 60)
    backfill()
