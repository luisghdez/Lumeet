"""
Carousel Image Generation Service

Generates educational carousel images for Instagram/TikTok using OpenAI.
Takes an initial prompt, generates a hook, individual slide prompts, and CTA prompt,
then creates images using OpenAI's image generation model.
"""

import os
import json
import base64
import re
from datetime import datetime
from typing import Any, Dict, Optional, List

from openai import OpenAI
import requests
from PIL import Image
import io

TEXT_MODEL_CANDIDATES = [
    os.environ.get("OPENAI_TEXT_MODEL", "gpt-5.4-2026-03-05"),
    "gpt-5-mini",
    "gpt-4.1",
]
IMAGE_MODEL_CANDIDATES = [
    os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1.5"),
    "gpt-image-1",
]
IMAGE_SIZE = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1536")


# ── Prompt Templates ────────────────────────────────────────────────────────────

HOOK_SLIDE_TEMPLATE = """Create a vertical 9:16 educational carousel cover slide in a bold modern flat cartoon style for Instagram or TikTok. Use a dark green background. Add very large cream-colored headline text reading: "{HEADLINE}". The text should take up most of the upper half and be extremely readable on mobile.

In the lower half, design a creative visual metaphor that communicates improvement, progress, or transformation in a bold and instantly understandable way. You may use one character, multiple poses, symbolic elements, or scene-based storytelling, but avoid repeating the exact same composition every time. Keep the illustration simple, clean, and visually bold with thick outlines and minimal clutter. Make it feel like a viral faceless educational carousel cover. Use Poppins Regular (font weight 400) for all hook text."""

INDIVIDUAL_SLIDE_TEMPLATE = """Design a vertical 9:16 Instagram carousel slide. Style: minimalist flat illustration, editorial and modern. Must NOT look AI-generated.

LAYOUT — three zones only, separated by generous empty space:

ZONE 1 — TOP THIRD:
Render "{NUMBER}" as a very large bold graphic numeral — treat it as a dominant design element that anchors the slide, not just a label. Below it, place the slide title in Poppins Bold: "{TIP_TITLE}". Title is maximum 2 lines, no wrapping.

ZONE 2 — MIDDLE (the illustration):
{SCENE_DESCRIPTION}. Flat vector style. Maximum 3 visual elements total in the scene. No background clutter. No secondary characters. No text inside the illustration. Leave at least 40% of this zone as intentional empty space around the focal element.

ZONE 3 — BOTTOM FIFTH:
Place this text in Poppins Regular directly on the background — no card, no box, no border, no shadow: "{EXPLANATION_TEXT}". Maximum 2 lines. Left-aligned or centered, clean.

DESIGN RULES — follow strictly:
- Background: a single solid color OR a clean 2-tone horizontal split. No gradients, no textures, no patterns.
- Color palette: 2-3 colors ONLY. The background color covers at least 55% of the slide.
- Typography: Poppins Bold for the number + title, Poppins Regular for the explanation text. No other typefaces.
- Illustration focal point: one primary element only — {EMOTION_MEANING}. Keep outlines clean and thick. No realistic shading.
- White space: deliberately generous. The slide should feel uncluttered and breathable.

DO NOT INCLUDE: speech bubbles, UI cards floating over illustrations, gradient backgrounds, realistic textures or lighting, complex crowd scenes, drop shadows on text, multiple characters competing for attention, decorative borders, clipart-style icons scattered around the slide."""

CTA_SLIDE_TEMPLATE = """Create a vertical 9:16 final CTA carousel slide in a bold modern flat cartoon style for Instagram or TikTok. Keep the same visual style, character design, and thick outlined illustration style as the earlier study carousel slides. Use a bright clean background, such as white or light cream, for contrast.

At the top, add very large bold text reading: "Download Lumi Learn".

Directly beneath or very close to the headline, include a clear App Store-style download badge with the Apple logo, so it is immediately understood that Lumi Learn is available on the App Store.

In the center, show the same cartoon student standing confidently beside an organized visual system made of flashcards, quiz cards, a study checklist, and neatly structured notes. The scene should visually communicate that studying is now easier, clearer, and more effective. Keep it clean, friendly, and highly readable.

Add a rounded white box near the bottom containing this exact text: "The easier way to study, review, and remember more."

Make the layout feel like a high-converting final carousel slide while staying fully illustrated and consistent with the previous slides. Use strong visual hierarchy, minimal clutter, mobile-first readability, and a polished viral carousel feel. Use Poppins font for all text."""


# ── System Prompt for Content Generation ────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert at creating minimalist educational carousel content for Instagram and TikTok. Your content will be rendered as flat-illustration slides in an editorial, modern style — NOT as detailed, complex illustrations.

Given an initial prompt (e.g., "a carousel giving 7 tips for more efficient studying"), you must:

1. Respect an explicit tip count when provided by the user
2. Otherwise choose between 5-8 tips based on the content
3. Generate a compelling hook headline for the cover slide
4. For each tip slide, generate content that fits a MINIMALIST 3-zone layout (big number + title, one focal illustration, one short text line)

Return your response as a JSON object with this exact structure:
{
  "num_slides": <number>,
  "hook_headline": "<compelling 6-10 word headline>",
  "slides": [
    {
      "number": 1,
      "tip_title": "<3-5 word tip title, punchy and direct>",
      "scene_description": "<describe ONE simple flat illustration — a single object, symbol, or minimal character moment. Max 20 words. No complex scenes.>",
      "visual_cues": "<ignored — left blank or N/A>",
      "emotion_meaning": "<one word or short phrase: the dominant feeling or concept this slide should convey>",
      "explanation_text": "<10-14 words max. One punchy sentence. No paragraph. Direct and impactful.>"
    },
    ...
  ]
}

Content quality rules:
- Hook headline: create curiosity, not clickbait. 6-10 words. Make it feel like the reader NEEDS to swipe.
- Tip titles: short, bold, scannable — 3 to 5 words. No filler.
- Scene descriptions: describe ONE minimal visual element only (e.g., "a single open book with a lightbulb above it", "a person sitting cross-legged with eyes closed, calm expression"). Avoid describing complex multi-element scenes or detailed backgrounds.
- Explanation text: MAXIMUM 14 words. One sentence. Should feel like a tweet, not a paragraph. Make it punchy and memorable.
- Vary the emotional tone across slides (some tense/negative to contrast with positive ones).
- Each slide scene should feel visually distinct from the others — avoid same composition twice.
"""


# ── Main Service Function ────────────────────────────────────────────────────────

def generate_carousel(
    initial_prompt: str,
    output_base_dir: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a complete carousel of educational images.

    Args:
        initial_prompt: The initial prompt describing the carousel content
                       (e.g., "a carousel giving 7 tips for more efficient studying")
        output_base_dir: Base directory for output. If None, uses backend/carousel_images/
        api_key: OpenAI API key. If None, uses OPENAI_API_KEY env var.

    Returns:
        A dict containing:
            - 'output_dir': Path to the output directory
            - 'hook_path': Path to the hook/cover slide image
            - 'slides': List of dicts with 'number', 'tip_title', and 'image_path'
            - 'cta_path': Path to the CTA slide image
            - 'all_prompts': Dict with all generated prompts for reference

    Raises:
        ValueError: If API key is missing
        RuntimeError: If image generation fails
    """
    # Validate API key
    api_key = _resolve_openai_api_key(api_key)
    if not api_key:
        raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY env var or pass api_key parameter.")

    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)

    # Determine output directory
    if output_base_dir is None:
        output_base_dir = os.path.join(os.path.dirname(__file__), "carousel_images")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(output_base_dir, timestamp)
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Generate content structure using chat API
    print(f"Generating carousel content from prompt: {initial_prompt}")
    content_structure = _generate_content_structure(client, initial_prompt)

    # Step 2: Build prompts from templates
    prompts = _build_prompts(content_structure)

    # Step 3: Generate images
    print(f"Generating {len(prompts)} images...")
    image_paths = _generate_images(client, prompts, output_dir)

    # Step 4: Build result structure
    result = {
        "output_dir": output_dir,
        "hook_path": image_paths["hook"],
        "slides": [
            {
                "number": slide["number"],
                "tip_title": slide["tip_title"],
                "image_path": image_paths[f"slide_{slide['number']}"],
            }
            for slide in content_structure["slides"]
        ],
        "cta_path": image_paths["cta"],
        "all_prompts": prompts,
    }

    print(f"✓ Carousel generation complete! Images saved to: {output_dir}")
    return result


# ── Helper Functions ─────────────────────────────────────────────────────────────

def _resolve_openai_api_key(explicit_api_key: Optional[str]) -> Optional[str]:
    """
    Resolve OpenAI API key from:
    1) explicit function argument
    2) OPENAI_API_KEY environment variable
    3) .env files (backend/.env then repo/.env)
    """
    if explicit_api_key and explicit_api_key.strip():
        return explicit_api_key.strip()

    env_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key

    backend_dir = os.path.dirname(__file__)
    repo_dir = os.path.dirname(backend_dir)
    for env_path in (
        os.path.join(backend_dir, ".env"),
        os.path.join(repo_dir, ".env"),
    ):
        value = _read_key_from_env_file(env_path, "OPENAI_API_KEY")
        if value:
            return value
    return None


def _read_key_from_env_file(env_file_path: str, key: str) -> Optional[str]:
    """Parse a dotenv-style file and return the value for a key if present."""
    if not os.path.isfile(env_file_path):
        return None

    try:
        with open(env_file_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                if "=" not in line:
                    continue
                lhs, rhs = line.split("=", 1)
                if lhs.strip() != key:
                    continue
                value = rhs.strip().strip("'\"")
                return value or None
    except OSError:
        return None

    return None

def _generate_content_structure(client: OpenAI, initial_prompt: str) -> Dict[str, Any]:
    """Generate the content structure using OpenAI chat API."""
    print("  Generating content structure...")

    requested_tip_count = _extract_explicit_tip_count(initial_prompt)
    user_instruction = (
        f"Initial prompt: {initial_prompt}\n"
        f"Requested tip count: {requested_tip_count if requested_tip_count is not None else 'none'}\n"
        "If requested tip count is provided, return exactly that many items in slides."
    )

    response = _responses_with_model_fallback(
        client=client,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_instruction,
    )

    content = _extract_response_text(response).strip()
    
    # Try to extract JSON from the response
    # Sometimes the model wraps JSON in markdown code blocks
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    try:
        structure = json.loads(content)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse content structure from OpenAI response: {e}\nResponse: {content}")
    
    # Validate structure
    if "num_slides" not in structure or "hook_headline" not in structure or "slides" not in structure:
        raise RuntimeError(f"Invalid content structure returned: {structure}")

    structure = _normalize_slide_count(structure, requested_tip_count)
    print(f"  ✓ Generated {structure['num_slides']} slides")
    return structure


def _build_prompts(content_structure: Dict[str, Any]) -> Dict[str, str]:
    """Build image generation prompts from content structure using templates."""
    prompts = {}
    
    # Hook slide
    prompts["hook"] = HOOK_SLIDE_TEMPLATE.format(
        HEADLINE=content_structure["hook_headline"]
    )
    
    # Individual slides
    for slide in content_structure["slides"]:
        prompts[f"slide_{slide['number']}"] = INDIVIDUAL_SLIDE_TEMPLATE.format(
            NUMBER=slide["number"],
            TIP_TITLE=slide["tip_title"],
            SCENE_DESCRIPTION=slide["scene_description"],
            VISUAL_CUES=slide["visual_cues"],
            EMOTION_MEANING=slide["emotion_meaning"],
            EXPLANATION_TEXT=slide["explanation_text"]
        )
    
    # CTA slide
    prompts["cta"] = CTA_SLIDE_TEMPLATE
    
    return prompts


def _generate_images(client: OpenAI, prompts: Dict[str, str], output_dir: str) -> Dict[str, str]:
    """Generate images using OpenAI image API and save them."""
    image_paths = {}
    
    # Generate hook image
    print("  Generating hook image...")
    hook_path = os.path.join(output_dir, "hook.png")
    _generate_single_image(client, prompts["hook"], hook_path)
    image_paths["hook"] = hook_path
    
    # Generate individual slide images
    slide_keys = sorted([k for k in prompts.keys() if k.startswith("slide_")])
    style_reference_path = None
    if slide_keys:
        first_slide_key = slide_keys[0]
        first_slide_num = first_slide_key.replace("slide_", "")
        print(f"  Generating slide {first_slide_num}...")
        first_slide_path = os.path.join(output_dir, f"slide_{first_slide_num}.png")
        _generate_single_image(client, prompts[first_slide_key], first_slide_path)
        image_paths[first_slide_key] = first_slide_path
        style_reference_path = first_slide_path

        for slide_key in slide_keys[1:]:
            slide_num = slide_key.replace("slide_", "")
            print(f"  Generating slide {slide_num}...")
            slide_path = os.path.join(output_dir, f"slide_{slide_num}.png")
            _generate_single_image(
                client,
                prompts[slide_key],
                slide_path,
                style_reference_path=style_reference_path,
            )
            image_paths[slide_key] = slide_path
    
    # Generate CTA image
    print("  Generating CTA image...")
    cta_path = os.path.join(output_dir, "cta.png")
    _generate_single_image(
        client,
        prompts["cta"],
        cta_path,
        style_reference_path=style_reference_path,
    )
    image_paths["cta"] = cta_path
    
    return image_paths


def _generate_single_image(
    client: OpenAI,
    prompt: str,
    output_path: str,
    style_reference_path: Optional[str] = None,
) -> None:
    """Generate a single image using OpenAI's GPT image models and save it."""
    try:
        response = _image_with_model_fallback(
            client=client,
            prompt=prompt,
            size=IMAGE_SIZE,
            style_reference_path=style_reference_path,
        )
        image_data = response.data[0]

        if getattr(image_data, "b64_json", None):
            raw_bytes = base64.b64decode(image_data.b64_json)
            image = Image.open(io.BytesIO(raw_bytes))
        elif getattr(image_data, "url", None):
            image_response = requests.get(image_data.url, timeout=60)
            image_response.raise_for_status()
            image = Image.open(io.BytesIO(image_response.content))
        else:
            raise RuntimeError("Image response did not contain url or b64_json.")

        image.save(output_path, "PNG")
        print(f"    ✓ Saved: {os.path.basename(output_path)}")
        
    except Exception as e:
        raise RuntimeError(f"Failed to generate image: {e}\nPrompt: {prompt[:100]}...")


def _responses_with_model_fallback(
    client: OpenAI,
    system_prompt: str,
    user_prompt: str,
):
    """Try newer text models first using the Responses API."""
    last_error = None
    seen = set()
    for model in TEXT_MODEL_CANDIDATES:
        if model in seen:
            continue
        seen.add(model)
        try:
            return client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
                ],
                reasoning={"effort": "medium"},
            )
        except Exception as exc:
            last_error = exc
            print(f"  Warning: text model '{model}' failed, trying fallback...")
    raise RuntimeError(f"All text model candidates failed: {last_error}")


def _extract_response_text(response: Any) -> str:
    """Extract text from a Responses API result, with fallback paths."""
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    output = getattr(response, "output", []) or []
    chunks: List[str] = []
    for item in output:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    if chunks:
        return "\n".join(chunks)

    raise RuntimeError("Responses API returned no text output.")


def _extract_explicit_tip_count(initial_prompt: str) -> Optional[int]:
    """Extract explicit tip count from prompt (e.g., '3 tips', 'seven tips')."""
    lowered = initial_prompt.lower()
    match = re.search(r"\b(\d{1,2})\s+(tips?|realizations?|lessons?|ways?)\b", lowered)
    if match:
        count = int(match.group(1))
        if 1 <= count <= 20:
            return count

    words_to_numbers = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    for word, number in words_to_numbers.items():
        if re.search(rf"\b{word}\s+(tips?|realizations?|lessons?|ways?)\b", lowered):
            return number
    return None


def _normalize_slide_count(
    structure: Dict[str, Any], requested_tip_count: Optional[int]
) -> Dict[str, Any]:
    """Ensure slide list length and numbering are consistent and respect explicit counts."""
    slides = structure.get("slides", [])
    if not isinstance(slides, list):
        raise RuntimeError("Invalid slides format returned by model.")

    target_count = requested_tip_count if requested_tip_count is not None else len(slides)
    if target_count <= 0:
        raise RuntimeError("Model returned no slides.")

    normalized = slides[:target_count]
    if len(normalized) < target_count and normalized:
        last = normalized[-1]
        while len(normalized) < target_count:
            clone = dict(last)
            clone["tip_title"] = f"{clone.get('tip_title', 'Tip')} (variant {len(normalized) + 1})"
            normalized.append(clone)

    for idx, slide in enumerate(normalized, start=1):
        slide["number"] = idx

    structure["slides"] = normalized
    structure["num_slides"] = len(normalized)
    return structure


def _image_with_model_fallback(
    client: OpenAI,
    prompt: str,
    size: str,
    style_reference_path: Optional[str] = None,
):
    """Try newer image models first, then fall back to compatible alternatives."""
    last_error = None
    seen = set()
    for model in IMAGE_MODEL_CANDIDATES:
        if model in seen:
            continue
        seen.add(model)
        try:
            if style_reference_path:
                # Reuse the first generated slide as a style reference for consistency.
                with open(style_reference_path, "rb") as reference_file:
                    try:
                        return client.images.edit(
                            model=model,
                            prompt=prompt,
                            size=size,
                            n=1,
                            image=reference_file,
                        )
                    except Exception:
                        reference_file.seek(0)
                        return client.images.edit(
                            model=model,
                            prompt=prompt,
                            size=size,
                            n=1,
                            image=[reference_file],
                        )
            return client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                n=1,
            )
        except Exception as exc:
            last_error = exc
            print(f"  Warning: image model '{model}' failed, trying fallback...")
    raise RuntimeError(f"All image model candidates failed: {last_error}")


# ── Standalone Testing ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python carousel_generator.py '<initial_prompt>'")
        print('Example: python carousel_generator.py "a carousel giving 7 tips for more efficient studying"')
        sys.exit(1)
    
    initial_prompt = sys.argv[1]
    
    try:
        result = generate_carousel(initial_prompt)
        print("\n" + "=" * 60)
        print("Generation Summary:")
        print("=" * 60)
        print(f"Output directory: {result['output_dir']}")
        print(f"Hook image: {result['hook_path']}")
        print(f"Number of slides: {len(result['slides'])}")
        for slide in result['slides']:
            print(f"  Slide {slide['number']}: {slide['tip_title']}")
        print(f"CTA image: {result['cta_path']}")
        print("=" * 60)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
