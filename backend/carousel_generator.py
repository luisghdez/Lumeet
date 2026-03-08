"""
Carousel Image Generation Service

Generates educational carousel images for Instagram/TikTok using OpenAI.
Takes an initial prompt, generates a hook, individual slide prompts, and CTA prompt,
then creates images using OpenAI's image generation model.
"""

import os
import json
import base64
from datetime import datetime
from typing import Any, Dict, Optional

from openai import OpenAI
import requests
from PIL import Image
import io

TEXT_MODEL_CANDIDATES = [
    os.environ.get("OPENAI_TEXT_MODEL", "gpt-5.3-chat-latest"),
    "gpt-4.1",
]
IMAGE_MODEL_CANDIDATES = [
    os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1.5"),
    "gpt-image-1",
]
IMAGE_SIZE = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1536")


# ── Prompt Templates ────────────────────────────────────────────────────────────

HOOK_SLIDE_TEMPLATE = """Create a vertical 9:16 educational carousel cover slide in a bold modern flat cartoon style for Instagram or TikTok. Use a dark green background. Add very large cream-colored headline text reading: "{HEADLINE}". The text should take up most of the upper half and be extremely readable on mobile.

In the lower half, show the same student in 3 stages from left to right: first overwhelmed and slouched, second unsure and improving, third confident and successful. Add a large upward arrow behind the character progression to symbolize growth and improvement. Keep the illustration simple, clean, and visually bold with thick outlines and minimal clutter. Make it feel like a viral faceless educational carousel cover. Use Poppins font for all text."""

INDIVIDUAL_SLIDE_TEMPLATE = """Create a vertical 9:16 educational carousel slide in a modern flat cartoon style for Instagram or TikTok. Use a bright sky-blue outdoor-style background or simple clean background that feels lighter than the cover slide. At the top, add large bold text reading: "{NUMBER}. {TIP_TITLE}".

Show a cartoon student in the center {SCENE_DESCRIPTION}. Add visual cues that {VISUAL_CUES}. The scene should instantly communicate {EMOTION_MEANING}.

Add a rounded white explanation box in the lower-middle area containing this exact text: "{EXPLANATION_TEXT}"

Use thick outlines, simple shapes, bold contrast, and a mobile-first layout. Keep the visual fun, clear, and highly readable. Use Poppins font for all text."""

CTA_SLIDE_TEMPLATE = """Create a vertical 9:16 final CTA carousel slide in a bold modern flat cartoon style for Instagram or TikTok. Keep the same visual style, character design, and thick outlined illustration style as the earlier study carousel slides. Use a bright clean background, such as white or light cream, for contrast.

At the top, add very large bold text reading: "Download Lumi Learn".

Directly beneath or very close to the headline, include a clear App Store-style download badge with the Apple logo, so it is immediately understood that Lumi Learn is available on the App Store.

In the center, show the same cartoon student standing confidently beside an organized visual system made of flashcards, quiz cards, a study checklist, and neatly structured notes. The scene should visually communicate that studying is now easier, clearer, and more effective. Keep it clean, friendly, and highly readable.

Add a rounded white box near the bottom containing this exact text: "The easier way to study, review, and remember more."

Make the layout feel like a high-converting final carousel slide while staying fully illustrated and consistent with the previous slides. Use strong visual hierarchy, minimal clutter, mobile-first readability, and a polished viral carousel feel. Use Poppins font for all text."""


# ── System Prompt for Content Generation ────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert at creating educational carousel content. Your task is to analyze an initial prompt and generate structured content for a carousel.

Given an initial prompt (e.g., "a carousel giving 7 tips for more efficient studying"), you must:

1. Determine the appropriate number of slides (between 5-8 based on the content)
2. Generate a compelling hook headline for the cover slide
3. Generate numbered tip titles and detailed explanations for each individual slide
4. Provide scene descriptions, visual cues, and emotion/meaning for each slide

Return your response as a JSON object with this exact structure:
{
  "num_slides": <number between 5-8>,
  "hook_headline": "<compelling headline for the cover slide>",
  "slides": [
    {
      "number": 1,
      "tip_title": "<short tip title>",
      "scene_description": "<detailed description of what the student is doing/feeling>",
      "visual_cues": "<description of visual elements like arrows, icons, etc.>",
      "emotion_meaning": "<what emotion or concept this slide communicates>",
      "explanation_text": "<the exact text to go in the white explanation box>"
    },
    ...
  ]
}

Important guidelines:
- The hook headline should be compelling and create curiosity
- Tip titles should be concise and actionable
- Scene descriptions should be detailed enough for image generation
- Visual cues should match the tip (e.g., circular arrows for repetition, checkmarks for success)
- Explanation text should be clear, concise, and educational
- Maintain consistency in the educational theme throughout"""


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
    
    response = _chat_with_model_fallback(
        client=client,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Initial prompt: {initial_prompt}"},
        ],
        temperature=0.7,
        max_tokens=2000,
    )

    content = response.choices[0].message.content.strip()
    
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
    
    if len(structure["slides"]) != structure["num_slides"]:
        print(f"  Warning: num_slides ({structure['num_slides']}) doesn't match slides array length ({len(structure['slides'])})")
    
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


def _chat_with_model_fallback(
    client: OpenAI,
    messages: list,
    temperature: float,
    max_tokens: int,
):
    """Try newer text models first, then fall back to compatible alternatives."""
    last_error = None
    seen = set()
    for model in TEXT_MODEL_CANDIDATES:
        if model in seen:
            continue
        seen.add(model)
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            last_error = exc
            print(f"  Warning: text model '{model}' failed, trying fallback...")
    raise RuntimeError(f"All text model candidates failed: {last_error}")


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
