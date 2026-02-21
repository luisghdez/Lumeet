"""
Caption Detection Service

Extracts on-screen captions from video frames by sending key frames
to OpenAI's GPT-4o Vision API, which can reason about the text and
return the exact caption — filtering out usernames and TikTok branding.
"""

import os
import re
import base64
import cv2
from openai import OpenAI


# ── Filtering (post-processing safety net) ────────────────────────────────────

BLOCKED_KEYWORDS = ["tiktok", "tik tok", "douyin"]
USERNAME_PATTERN = re.compile(r"@\w+", re.IGNORECASE)


def _contains_blocked_keyword(text):
    lower = text.lower()
    return any(kw in lower for kw in BLOCKED_KEYWORDS)


def _contains_username(text):
    return bool(USERNAME_PATTERN.search(text))


def clean_caption(text):
    """
    Post-process a caption returned by the model:
    - Strip @usernames
    - Remove lines that are just TikTok branding
    - Return None if nothing useful remains
    """
    if not text or not text.strip():
        return None

    lines = text.strip().splitlines()
    cleaned_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if _contains_blocked_keyword(line):
            continue
        # Strip usernames from the line
        line = USERNAME_PATTERN.sub("", line).strip()
        if line:
            cleaned_lines.append(line)

    result = "\n".join(cleaned_lines).strip()
    return result if result else None


# ── Frame extraction ──────────────────────────────────────────────────────────

def extract_frames(video_path, interval_sec=1.0):
    """
    Extract frames from a video at a given interval using OpenCV.

    Returns list of (timestamp_sec, frame_ndarray) tuples.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    frame_interval = max(1, int(fps * interval_sec))
    frames = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_interval == 0:
            timestamp = frame_idx / fps
            frames.append((timestamp, frame))
        frame_idx += 1

    cap.release()
    return frames


def frame_to_base64(frame):
    """Encode an OpenCV frame as a base64 JPEG string."""
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buffer).decode("utf-8")


def pick_best_frames(frames, max_frames=3):
    """
    Pick a few representative frames for caption reading.

    Strategy: grab frames from the second half of the clip where
    on-screen text is most likely fully rendered / visible.
    """
    if not frames:
        return []

    n = len(frames)
    if n <= max_frames:
        return frames

    # Take frames from the latter portion of the video
    half = n // 2
    latter = frames[half:]

    if len(latter) <= max_frames:
        return latter

    # Evenly space within the latter half
    step = max(1, len(latter) // max_frames)
    selected = latter[::step][:max_frames]
    return selected


# ── OpenAI Vision API call ────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a video caption reader. You will be shown frames from a short video clip.

Your task:
1. Read the on-screen caption/text that appears overlaid on the video.
2. Return ONLY the exact caption text, cleaned up and complete.

Rules:
- IGNORE any usernames (text starting with @).
- IGNORE "TikTok" branding, logos, or watermarks.
- IGNORE UI elements like like counts, share buttons, comments, etc.
- Focus ONLY on the main caption/subtitle text shown on screen.
- If the text is split across multiple frames (e.g. appearing word by word), combine it into the full sentence.
- Return the caption exactly as written — preserve capitalisation, punctuation, emojis.
- If there is no caption text visible, respond with exactly: NO_CAPTION
- Return ONLY the caption text, nothing else. No quotes, no explanations."""


def detect_captions(video_path, interval_sec=0.5, api_key=None):
    """
    Detect on-screen captions in a video using OpenAI Vision.

    Extracts key frames, sends them to GPT-4o, and returns the
    detected caption with TikTok/username filtering applied.

    Args:
        video_path: Path to the video file.
        interval_sec: Seconds between sampled frames (default 0.5).
        api_key: OpenAI API key. If None, uses OPENAI_API_KEY env var.

    Returns:
        A dict with:
            - 'caption': the detected caption text (or None)
            - 'frames_analysed': number of frames sent to the model
        or None if no caption was found.

    Raises:
        FileNotFoundError: If the video file does not exist.
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Extract and pick best frames
    all_frames = extract_frames(video_path, interval_sec=interval_sec)
    selected = pick_best_frames(all_frames, max_frames=3)

    if not selected:
        return None

    # Build the vision message with multiple frames
    image_content = []
    for ts, frame in selected:
        b64 = frame_to_base64(frame)
        image_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "detail": "low",   # cheaper, sufficient for large text
            },
        })

    user_message = [
        {"type": "text", "text": "Read the on-screen caption from these video frames. Ignore any @usernames and TikTok branding."},
    ] + image_content

    # Call OpenAI
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=200,
        temperature=0,
    )

    raw_text = response.choices[0].message.content.strip()

    # Handle no-caption response
    if raw_text == "NO_CAPTION":
        return {"caption": None, "frames_analysed": len(selected)}

    # Post-process as a safety net
    caption = clean_caption(raw_text)

    return {
        "caption": caption,
        "frames_analysed": len(selected),
    }


def detect_captions_summary(video_path, interval_sec=0.5, api_key=None):
    """
    High-level wrapper: returns just the caption string, or None.
    """
    result = detect_captions(video_path, interval_sec=interval_sec, api_key=api_key)
    if result is None:
        return None
    return result.get("caption")
