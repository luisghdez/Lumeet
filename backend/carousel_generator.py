"""
Carousel Image Generation Service

Generates educational carousel images for Instagram/TikTok using OpenAI.
Takes an initial prompt, generates a hook and individual slide images using OpenAI.
The CTA slide is always picked randomly from the static assets in backend/input/.
"""

import os
import json
import base64
import re
import random
import shutil
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
IMAGE_SIZE = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024")


# ── Prompt Templates ────────────────────────────────────────────────────────────

HOOK_SLIDE_TEMPLATE_ILLUSTRATED = """Design a square 1:1 TikTok/Instagram carousel cover slide. Style: minimalist flat illustration, editorial and modern. Must NOT look AI-generated.

LAYOUT — two zones only, separated by generous empty space:

ZONE 1 — LEFT OR TOP HALF:
Place the headline in Poppins Bold, very large, light-colored text on a deep dark background: "{HEADLINE}". The headline is the hero of this slide — it should dominate and be instantly readable at thumbnail size. Maximum 2 lines. No decorative elements competing with the text.

ZONE 2 — RIGHT OR BOTTOM HALF (the illustration):
One single flat illustration that visually represents the theme of the headline. Choose ONE of these creative directions — do not default to the same every time:
- A single symbolic object (e.g., a cracked clock, a glowing book, a maze with one clear exit)
- A minimal abstract shape composition (e.g., upward geometric forms, a clean progress arc)
- A single faceless character in one decisive moment (e.g., standing at a crossroads, looking upward, holding something meaningful)
Leave at least 40% of this zone as empty background. The illustration is a supporting accent, not the main event.

DESIGN RULES — follow strictly:
- Background: choose a bold, deep background color that fits the mood and topic. Good options include deep navy, dark charcoal, rich burgundy, dark forest green, deep violet, dark teal — vary it creatively. Solid color only. No gradients, no textures, no patterns.
- Text color: use a high-contrast light color that pairs well with your chosen background — cream, soft white, pale yellow, or light coral. NOT always cream on green.
- Color palette: background + contrasting text color + ONE accent color for the illustration. Maximum 3 colors total.
- Typography: Poppins Bold (weight 700) for the headline. Poppins Regular (weight 400) for any secondary text. No other typefaces.
- Illustration: flat vector, thick clean outlines, minimal details. One focal element only.
- White space: the slide should feel uncluttered and bold — like a high-end editorial cover.

DO NOT INCLUDE: character progression sequences (multiple poses), upward arrows with multiple figures, paragraph text below the headline, rounded cards or UI boxes, gradient backgrounds, decorative borders, multiple competing illustration elements, speech bubbles, drop shadows on text, always defaulting to dark green — vary the background color every time."""

HOOK_SLIDE_TEMPLATE_STUDY_DESK = """Generate a square 1:1 TikTok/Instagram carousel cover photo. Style: a REAL Pinterest-aesthetic study desk flatlay photograph. Must look like a real photograph taken by a lifestyle content creator — NOT AI-generated, NOT illustrated.

THE SCENE — a beautifully styled overhead (bird's-eye) or slightly angled shot of an aesthetic study desk:
- An open notebook or planner with handwritten-style notes visible
- Pastel-colored stationery: highlighters, pens, washi tape, sticky notes
- A warm drink — matcha latte, iced coffee, or a cute mug of tea
- Soft ambient lighting: fairy lights, a candle, or warm golden-hour window light
- Optional cozy touches: a small plant, dried flowers, a knit sweater draped on the chair
- The desk surface should be clean wood, white marble, or light-colored — bright and airy

TEXT OVERLAY — the hook headline:
Render this text as a bold overlay on the image: "{HEADLINE}"
- Use a clean sans-serif font (like Poppins Bold or Montserrat Bold), large enough to read at thumbnail size.
- Text color: white or cream with a subtle drop shadow or semi-transparent dark background strip behind the text for readability.
- Position the text in the center or upper-third of the image so it dominates.
- Maximum 2 lines of text.

PHOTOGRAPHIC RULES — follow strictly:
- This must look like a REAL photograph, shot on an iPhone or DSLR. Shallow depth of field is fine.
- Color palette: warm, soft, muted tones — think beige, blush pink, sage green, cream, dusty rose, soft brown. Pinterest-worthy aesthetic.
- Lighting: soft natural light or warm fairy-light glow. No harsh shadows, no flash.
- Composition: flatlay or 45-degree angle. The desk should feel organized but lived-in — styled but not sterile.
- The overall mood: cozy, aspirational, motivating — the kind of image someone saves on Pinterest.

DO NOT INCLUDE: messy desks, dark or dim lighting, cluttered backgrounds, neon colors, cartoon elements, illustrated graphics, stock-photo-looking setups, computer screens or phones as the main subject, people's faces."""

HOOK_SLIDE_TEMPLATE_STUDY_GIRL = """Generate a square 1:1 TikTok/Instagram carousel cover photo. Style: a REAL candid photograph that looks like it was taken by a TikTok or Instagram content creator — authentic, natural, NOT AI-generated, NOT illustrated, NOT stock photography.

THE SCENE — pick ONE of these scene types at random (VARY every time, never repeat the same setup):

OPTION A – LIBRARY PORTRAIT: A young woman sitting casually in a beautiful old library or reading room. She is relaxed — chin resting on her hand, leaning back in a leather chair or wooden seat. Bookshelves fill the background. A laptop or open book is in front of her. She looks directly at the camera with a natural, relaxed expression — like a friend snapped this photo of her. The library should feel grand and atmospheric (dark wood, warm lamp light, tall shelves).

OPTION B – BETWEEN THE BOOKSHELVES: Close-up portrait of a young woman standing or leaning between library bookshelves. She faces the camera with a soft, natural expression — chin on hands, or leaning against the shelf. The bookshelves stretch behind her creating depth. Tight framing, intimate and candid. Soft natural light or warm overhead library lighting.

OPTION C – STUDY TABLE CANDID: A young woman at a study table or café, seen from across the table. Books, notebooks, phone, or a drink are scattered naturally in front of her. She could be wearing headphones or have them around her neck. She looks up from studying toward the camera — a casual, caught-in-the-moment feel. A friend might be partially visible at the edge of the frame.

OPTION D – COZY STUDY NOOK: A young woman curled up in a window seat, beanbag, or cozy corner with books and notes around her. Warm natural light from a window. She glances at the camera with a natural smile or focused expression. Oversized sweater or hoodie, cozy vibes.

WARDROBE & STYLING (vary each time):
- Oversized knit sweaters, hoodies, cardigans in muted tones (cream, gray, blue, sage, dusty pink)
- Casual accessories: headphones (over-ear or around neck), simple jewelry, glasses
- Hair styled naturally — not overly done
- The person should look like a real university student or young content creator, not a model

TEXT OVERLAY — the hook headline:
Render this text as a bold overlay on the image: "{HEADLINE}"
- Use a thick, heavy sans-serif font (like Poppins ExtraBold, Montserrat Black, or similar chunky typeface).
- Text must be LARGE — at least 30-40% of the image width — and instantly readable at thumbnail size on a phone screen.
- CRITICAL TEXT STYLING — pick ONE of these text treatments (vary each time):
  1. HIGHLIGHTED WORDS: Render 1-2 key words with a bright solid-color highlight box behind them (yellow, coral, mint green, or light blue) while the rest of the text is clean white with a subtle drop shadow. This creates the viral TikTok "highlighted keyword" look.
  2. ALL-CAPS BOLD WHITE: All text in white with a strong drop shadow or thin dark outline for readability. Key words can be slightly larger or on their own line for emphasis.
  3. MIXED CASE WITH COLOR POP: Most text in white, but one power word rendered in a bright accent color (yellow, coral, electric blue) to draw the eye.
- Position the text in the CENTER of the image vertically, or slightly above center.
- Maximum 3 lines. Each line should be punchy and short.
- If the headline contains emoji, render the emoji inline with the text.

PHOTOGRAPHIC RULES — follow strictly:
- This MUST look like a real candid photograph taken on an iPhone by a friend or with a self-timer. NOT a professional studio shot.
- The person CAN and SHOULD face the camera — natural, relaxed expression. This is NOT a faceless aesthetic.
- Shallow depth of field with soft bokeh background is ideal.
- Lighting: warm natural light (golden hour, window light), or atmospheric library lighting (warm overhead lamps, reading lights). NEVER harsh fluorescent or flash.
- Color grading: warm, slightly desaturated tones — the "TikTok study" color palette. Think warm browns, creams, soft greens, muted blues. The image should feel cozy and inviting.
- The composition should feel spontaneous, not staged — like a real moment captured.
- The person should be the clear subject, with the study environment providing context and atmosphere.

DO NOT INCLUDE: stock-photo-looking poses (hands on hips, corporate smiles), sterile/clean environments, harsh lighting, neon colors, cartoon or illustrated elements, overly posed or model-like compositions, AI-looking faces or hands, perfectly symmetrical compositions, clipart or graphic overlays, thin or small text that can't be read at thumbnail size."""

HOOK_SLIDE_TEMPLATE_PINTEREST = """Create a 9:9 Pinterest-style study image that looks like a real lifestyle photo with text overlay.

GOAL:
- The image must feel human, candid, and save-worthy for social media.
- Avoid anything staged, over-polished, or obvious AI artifacts.

TYPOGRAPHY RULES (MANDATORY):
- Overlay text must say exactly: "{HEADLINE}"
- Use a bold geometric sans-serif style (Poppins ExtraBold feel).
- Thick white text with a subtle soft gray shadow for readability.
- Keep the highlight rectangle flat and clean: no rounded corners, no glow, no effects.
- Use a stacked social-media text layout (centered or slightly offset like TikTok edits).
- Preserve natural negative space around subject and text.

PHOTO STYLE RULES (MANDATORY):
- Organic iPhone mirror/lifestyle photo look.
- Slight grain, warm tones, soft natural shadows.
- Realistic imperfections in composition and environment.
- Not overly sharp and not studio quality.
- Room/scene should look lived-in and believable.
"""

# Study-girl realism and diversity controls (selected in code per generation)
_STUDY_GIRL_SCENES = [
    "library reading table with stacked books and warm desk lamps in frame",
    "narrow aisle between bookshelves with depth and foreground blur",
    "cozy cafe corner near a window with notebook, cup, and backpack",
    "university common area with soft daylight and classmates blurred in background",
    "window-seat study nook with books and a blanket nearby",
    "bedroom desk setup at home with fairy lights, planner, and laptop",
    "full-length mirror corner at home with a study desk reflected behind her",
    "library staircase landing with books and tote bag, candid lifestyle vibe",
    "kitchen island at home turned into a temporary study station",
    "quiet classroom after hours with notebooks spread out and soft ambient light",
]

_STUDY_GIRL_SUBJECTS = [
    "young woman (early 20s), East Asian features, natural makeup, student vibe",
    "young woman (early 20s), Latina features, minimal makeup, student vibe",
    "young woman (early 20s), South Asian features, minimal makeup, student vibe",
    "young woman (early 20s), Black features, minimal makeup, student vibe",
    "young woman (early 20s), white features, minimal makeup, student vibe",
    "young woman (early 20s), Middle Eastern features, minimal makeup, student vibe",
]

_STUDY_GIRL_POSES = [
    "looking up from writing notes, pen still in hand, soft half-smile",
    "chin resting on one hand while reading, relaxed eye contact with camera",
    "adjusting headphones around her neck, candid expression, mid-movement",
    "holding an open book against her chest, casual stance, natural eye contact",
    "typing on laptop then glancing at camera, caught-in-the-moment feel",
    "arm extended taking a close selfie, natural smile, candid social vibe",
    "mirror selfie pose with phone in hand, relaxed body angle, not over-posed",
    "playful kissy-face expression for one quick frame, still natural and believable",
    "laughing while talking with a friend, looking briefly toward the camera",
    "walking between shelves while turning back toward camera mid-step",
]

_STUDY_GIRL_CAMERA_SETUPS = [
    "eye-level medium shot, 35mm lens look, shallow depth of field, slight handheld feel",
    "close-up portrait, 50mm lens look, focus on eyes, soft background bokeh",
    "slightly high angle from across the table, 35mm lens look, natural perspective",
    "over-the-shoulder framing with subject turning toward camera, shallow depth of field",
    "very close selfie framing, phone-camera perspective, realistic slight distortion",
    "mirror-photo composition with subject and room visible, natural phone framing",
    "wide environmental shot from farther away showing full body and room context",
    "tight crop on face and hands with shallow depth for intimate candid feel",
]

_STUDY_GIRL_LIGHTING = [
    "soft window light from camera-left with gentle falloff and realistic shadow gradients",
    "warm practical lamp light with subtle ambient daylight balancing from background",
    "golden-hour side light, soft contrast, no clipped highlights, no harsh shadows",
    "moody dark lighting with a single warm desk lamp and visible shadow depth",
    "low-light evening scene with practical lights only, realistic phone-camera noise level",
    "bright airy daylight with soft bounce light and clean color tones",
]

_STUDY_GIRL_STYLING = [
    "oversized knit sweater in cream + simple necklace + neutral notebook",
    "muted hoodie in sage or dusty blue + thin-frame glasses + highlighters on desk",
    "cardigan layered over basic tee + messy bun + sticky notes and tabs visible",
    "cozy sweatshirt + over-ear headphones + iced coffee and planner in frame",
    "simple going-out outfit plus tote bag and textbook stack for campus vibe",
    "at-home comfy set with claw clip hairstyle and cozy socks visible in frame",
]

_STUDY_GIRL_TEXT_TREATMENTS = [
    "highlight 1-2 keywords with a yellow or mint rectangle behind text",
    "all-caps heavy white text with thin dark stroke for readability",
    "mostly white text with one accent word in coral or electric blue",
]

_STUDY_GIRL_COMPOSITIONS = [
    "solo: one subject only, clear focal person",
    "duo: subject with one friend, both candid and natural",
    "group: 3-4 students in frame with one primary subject still clearly dominant",
]

_PINTEREST_SCENES = [
    (
        "mirror selfie (relatable)",
        "A college girl taking a casual mirror selfie in her room. In the reflection, show a cozy study setup "
        "with an open laptop, notebook, highlighter, and coffee. Room feels lived-in, slightly messy but aesthetic, "
        "warm natural window light.",
    ),
    (
        "desk focus (aspirational)",
        "A student-focused desk scene as a realistic lifestyle photo, with active study materials, natural clutter, "
        "and warm daylight. Subject appears candid in-frame, not posed.",
    ),
    (
        "bed study (cozy)",
        "A girl studying on her bed with laptop, notebook, and coffee or matcha. Cozy lamp + warm tones, slightly "
        "messy blankets, realistic late-night study mood.",
    ),
    (
        "library (productive)",
        "A candid library moment with a student actively studying at a table, books and notes spread naturally, "
        "ambient warm practical lighting and real-world imperfections.",
    ),
    (
        "coffee shop (aesthetic)",
        "A real cafe study moment with notebook, drink, and laptop, shallow depth and natural scene clutter. "
        "Looks like an organic social photo, not a commercial shoot.",
    ),
    (
        "messy floor (real)",
        "A guy sitting on the floor with papers spread out, laptop nearby, and backpack next to him. "
        "He is holding a pen or looking at notes, stressed-but-productive candid study moment with imperfect composition.",
    ),
]

# ── Hook Style Registry ──────────────────────────────────────────────────────────

HOOK_STYLES = {
    "illustrated": HOOK_SLIDE_TEMPLATE_ILLUSTRATED,
    "study_desk": HOOK_SLIDE_TEMPLATE_STUDY_DESK,
    "study_girl": HOOK_SLIDE_TEMPLATE_STUDY_GIRL,
    "pinterest": HOOK_SLIDE_TEMPLATE_PINTEREST,
}
DEFAULT_HOOK_STYLE = "illustrated"

INDIVIDUAL_SLIDE_TEMPLATE = """Design a square 1:1 TikTok/Instagram carousel slide. Style: minimalist flat illustration, editorial and modern. Must NOT look AI-generated.

LAYOUT — three zones only, separated by generous empty space:

ZONE 1 — TOP QUARTER:
Render "{NUMBER}" as a very large bold graphic numeral — treat it as a dominant design element that anchors the slide, not just a label. Beside or below it, place the slide title in Poppins Bold: "{TIP_TITLE}". Title is maximum 2 lines, no wrapping.

ZONE 2 — CENTER (the illustration):
{SCENE_DESCRIPTION}. Flat vector style. Maximum 3 visual elements total in the scene. No background clutter. No secondary characters. No text inside the illustration. Leave at least 40% of this zone as intentional empty space around the focal element.

ZONE 3 — BOTTOM STRIP:
Place this text in Poppins Regular directly on the background — no card, no box, no border, no shadow: "{EXPLANATION_TEXT}". Maximum 1 line. Left-aligned or centered, clean.

DESIGN RULES — follow strictly:
- Background: a single solid color OR a clean 2-tone horizontal split. No gradients, no textures, no patterns.
- Color palette: 2-3 colors ONLY. The background color covers at least 55% of the slide.
- Typography: Poppins Bold for the number + title, Poppins Regular for the explanation text. No other typefaces.
- Illustration focal point: one primary element only — {EMOTION_MEANING}. Keep outlines clean and thick. No realistic shading.
- White space: deliberately generous. The slide should feel uncluttered and breathable.

DO NOT INCLUDE: speech bubbles, UI cards floating over illustrations, gradient backgrounds, realistic textures or lighting, complex crowd scenes, drop shadows on text, multiple characters competing for attention, decorative borders, clipart-style icons scattered around the slide."""

INDIVIDUAL_SLIDE_TEMPLATE_ILLUSTRATED_2 = """Create a 9:9 social-media educational carousel slide for a study app.

STYLE:
- Save-worthy mini lesson for Instagram/TikTok.
- Clean, structured, educational.
- Illustration/layout based (not lifestyle photography).
- Modern flat visual language, premium but not corporate.
- Strong visual hierarchy and generous spacing.
- Easy to scan quickly.

LAYOUT:
- Headline (large, bold): "{TIP_TITLE}"
- Support line below headline: "{EXPLANATION_TEXT}"
- Section label: "WHY IT WORKS"
- Add exactly 3 short bullet-style points with small flat icons/illustrations:
  1) {WHY_POINT_1}
  2) {WHY_POINT_2}
  3) {WHY_POINT_3}

VISUAL ELEMENTS:
- Include subtle study-app cues like flashcards, quiz cards, or note cards.
- Keep iconography simple, flat, and coherent with the slide.
- Use teal accent/highlight bars sparingly for emphasis.

TYPOGRAPHY:
- Bold geometric sans serif style similar to Poppins.
- Clear heading, readable support text, clean spacing.

DO NOT INCLUDE:
- Lifestyle-photo-only Pinterest aesthetics.
- Cluttered infographic overload.
- Generic startup ad look.
- Decorative noise or excessive ornament.
"""

CAROUSEL_STYLES = {
    "illustrated": INDIVIDUAL_SLIDE_TEMPLATE,
    "illustrated_2": INDIVIDUAL_SLIDE_TEMPLATE_ILLUSTRATED_2,
}
DEFAULT_CAROUSEL_STYLE = "illustrated"

# Static CTA images — randomly selected from backend/input/ instead of AI-generated
_CTA_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "input")
_CTA_FILENAMES = ["cta_1.png", "cta_2.png"]


# ── System Prompt for Content Generation ────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert at creating viral, scroll-stopping educational carousel content for Instagram and TikTok. Your content will be rendered as flat-illustration slides in an editorial, modern style — NOT as detailed, complex illustrations.

Given an initial prompt (e.g., "a carousel giving 7 tips for more efficient studying"), you must:

1. Respect an explicit tip count when provided by the user
2. Otherwise choose between 5-8 tips based on the content
3. Set the hook_headline to be the EXACT text from the user's prompt — copy it WORD FOR WORD. Do NOT rephrase, rewrite, or generate a different headline. The user's prompt IS the hook headline.
4. For each tip slide, generate content that fits a MINIMALIST 3-zone layout (big number + title, one focal illustration, one short text line)

Return your response as a JSON object with this exact structure:
{
  "num_slides": <number>,
  "hook_headline": "<the user's EXACT prompt text, copied verbatim>",
  "slides": [
    {
      "number": 1,
      "tip_title": "<3-5 word tip title, punchy and direct>",
      "scene_description": "<describe ONE simple flat illustration — a single object, symbol, or minimal character moment. Max 20 words. No complex scenes.>",
      "visual_cues": "<ignored — left blank or N/A>",
      "emotion_meaning": "<one word or short phrase: the dominant feeling or concept this slide should convey>",
      "explanation_text": "<10-14 words max. One punchy sentence. No paragraph. Direct and impactful.>",
      "why_it_works_points": [
        "<short bullet 1, 3-7 words>",
        "<short bullet 2, 3-7 words>",
        "<short bullet 3, 3-7 words>"
      ]
    },
    ...
  ]
}

HOOK HEADLINE — CRITICAL RULE:
- The hook_headline MUST be the EXACT text the user typed in their prompt. Copy it character-for-character.
- Do NOT rephrase it, do NOT make it "more viral", do NOT apply any formula to it.
- The user has already written the hook they want. Respect it exactly.
- If the prompt includes emoji, keep the emoji. If it includes punctuation, keep the punctuation.

Content quality rules:
- Tip titles: short, bold, scannable — 3 to 5 words. No filler.
- Scene descriptions: describe ONE minimal visual element only (e.g., "a single open book with a lightbulb above it", "a person sitting cross-legged with eyes closed, calm expression"). Avoid describing complex multi-element scenes or detailed backgrounds.
- Explanation text: MAXIMUM 14 words. One sentence. Should feel like a tweet, not a paragraph. Make it punchy and memorable.
- why_it_works_points: exactly 3 concise, non-redundant bullet phrases per slide.
- Vary the emotional tone across slides (some tense/negative to contrast with positive ones).
- Each slide scene should feel visually distinct from the others — avoid same composition twice.
"""


# ── Main Service Function ────────────────────────────────────────────────────────

def generate_carousel(
    initial_prompt: str,
    output_base_dir: Optional[str] = None,
    api_key: Optional[str] = None,
    hook_style: str = DEFAULT_HOOK_STYLE,
    carousel_style: str = DEFAULT_CAROUSEL_STYLE,
) -> Dict[str, Any]:
    """
    Generate a complete carousel of educational images.

    Args:
        initial_prompt: The initial prompt describing the carousel content
                       (e.g., "a carousel giving 7 tips for more efficient studying")
        output_base_dir: Base directory for output. If None, uses backend/carousel_images/
        api_key: OpenAI API key. If None, uses OPENAI_API_KEY env var.
        hook_style: Style for the hook/cover slide image. One of "illustrated",
                    "study_desk", "study_girl", or "pinterest". Defaults to "illustrated".
        carousel_style: Style for individual content slides. One of "illustrated"
                        or "illustrated_2". Defaults to "illustrated".

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
    prompts = _build_prompts(
        content_structure,
        hook_style=hook_style,
        carousel_style=carousel_style,
    )

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


def _build_prompts(
    content_structure: Dict[str, Any],
    hook_style: str = DEFAULT_HOOK_STYLE,
    carousel_style: str = DEFAULT_CAROUSEL_STYLE,
) -> Dict[str, str]:
    """Build image generation prompts from content structure using templates."""
    prompts = {}
    
    # Hook slide — select template based on hook_style
    prompts["hook"] = _build_hook_prompt(
        headline=content_structure["hook_headline"],
        hook_style=hook_style,
    )
    
    # Individual slides
    slide_template = CAROUSEL_STYLES.get(
        carousel_style,
        CAROUSEL_STYLES[DEFAULT_CAROUSEL_STYLE],
    )
    for slide in content_structure["slides"]:
        why_points = _derive_why_points(slide)
        prompts[f"slide_{slide['number']}"] = slide_template.format(
            NUMBER=slide["number"],
            TIP_TITLE=slide["tip_title"],
            SCENE_DESCRIPTION=slide["scene_description"],
            VISUAL_CUES=slide.get("visual_cues", ""),
            EMOTION_MEANING=slide.get("emotion_meaning", ""),
            EXPLANATION_TEXT=slide["explanation_text"],
            WHY_POINT_1=why_points[0],
            WHY_POINT_2=why_points[1],
            WHY_POINT_3=why_points[2],
        )
    
    return prompts


def _build_hook_prompt(headline: str, hook_style: str = DEFAULT_HOOK_STYLE) -> str:
    """Build hook prompt and inject style-specific controls."""
    hook_template = HOOK_STYLES.get(hook_style, HOOK_STYLES[DEFAULT_HOOK_STYLE])
    prompt = hook_template.format(HEADLINE=headline)
    if hook_style == "study_girl":
        prompt = f"{prompt}\n\n{_build_study_girl_variation_block()}"
    if hook_style == "pinterest":
        prompt = f"{prompt}\n\n{_build_pinterest_variation_block()}"
    return prompt


def _derive_why_points(slide: Dict[str, Any]) -> List[str]:
    """Create 3 concise 'why it works' bullets for structured slide styles."""
    provided = slide.get("why_it_works_points")
    if isinstance(provided, list):
        normalized = [str(item).strip() for item in provided if str(item).strip()]
        if len(normalized) >= 3:
            return normalized[:3]

    explanation = str(slide.get("explanation_text", "")).strip().rstrip(".")
    emotion = str(slide.get("emotion_meaning", "")).strip()
    scene = str(slide.get("scene_description", "")).strip().rstrip(".")

    p1 = explanation if explanation else "strengthens memory retrieval"
    if len(p1) > 58:
        p1 = p1[:58].rstrip() + "..."
    p2 = f"reinforces {emotion.lower()} through repetition" if emotion else "exposes weak areas fast"
    p3 = "makes studying easier to repeat consistently"
    if scene:
        p3 = f"connects ideas to a concrete cue: {scene[:42].rstrip()}"
    return [p1, p2, p3]


def _build_study_girl_variation_block() -> str:
    """
    Inject explicit non-repetitive choices so each study-girl hook changes:
    subject profile, pose, scene, camera setup, lighting, and text treatment.
    """
    scene = random.choice(_STUDY_GIRL_SCENES)
    subject = random.choice(_STUDY_GIRL_SUBJECTS)
    pose = random.choice(_STUDY_GIRL_POSES)
    camera_setup = random.choice(_STUDY_GIRL_CAMERA_SETUPS)
    lighting = random.choice(_STUDY_GIRL_LIGHTING)
    styling = random.choice(_STUDY_GIRL_STYLING)
    text_treatment = random.choice(_STUDY_GIRL_TEXT_TREATMENTS)
    composition = random.choice(_STUDY_GIRL_COMPOSITIONS)
    variation_id = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{random.randint(100, 999)}"

    return (
        "REALISM + VARIATION BLUEPRINT (MANDATORY):\n"
        f"- Variation ID: {variation_id}\n"
        f"- Exact subject profile to depict: {subject}\n"
        f"- Exact environment to depict: {scene}\n"
        f"- Exact candid action/pose: {pose}\n"
        f"- Camera direction: {camera_setup}\n"
        f"- Lighting direction: {lighting}\n"
        f"- Wardrobe/props direction: {styling}\n"
        f"- People composition mode: {composition}\n"
        f"- Text treatment to apply: {text_treatment}\n"
        "- Render as smartphone/DSLR photo realism: natural skin texture, realistic pores,"
        " tiny hair flyaways, natural fabric folds, physically plausible shadows,"
        " believable perspective, no waxy skin.\n"
        "- Candid social-photo energy is welcome (selfie, mirror pic, close shot, far shot),"
        " but keep anatomy and perspective realistic.\n"
        "- No duplicated limbs, no extra fingers, no warped text,"
        " no AI artifacts. If conflict exists, this blueprint overrides generic defaults."
    )


def _build_pinterest_variation_block() -> str:
    """Rotate Pinterest hook setups so generated covers feel human and non-repetitive."""
    scene_label, scene_instruction = random.choice(_PINTEREST_SCENES)
    variation_id = datetime.now().strftime("%Y%m%d-%H%M%S") + f"-{random.randint(100, 999)}"
    return (
        "PINTEREST REALISM BLUEPRINT (MANDATORY):\n"
        f"- Variation ID: {variation_id}\n"
        f"- Rotating scene selected: {scene_label}\n"
        f"- Exact scene direction: {scene_instruction}\n"
        "- Keep subject candid and imperfect (not ad-like, not model-polished).\n"
        "- Maintain warm natural light and subtle film grain.\n"
        "- Composition should feel authentic: slightly off-center or naturally framed.\n"
        "- Keep typography clean and social-native; text must remain instantly readable."
    )


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
    
    # Use a static CTA image (randomly pick cta_1.png or cta_2.png)
    chosen_cta_filename = random.choice(_CTA_FILENAMES)
    chosen_cta_src = os.path.join(_CTA_ASSETS_DIR, chosen_cta_filename)
    cta_path = os.path.join(output_dir, "cta.png")
    print(f"  Using static CTA image: {chosen_cta_filename}")
    shutil.copy2(chosen_cta_src, cta_path)
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
