"""
Scene Recreator Service (Gemini Nano Banana Pro)

Takes a scene screenshot and a model identity image, then uses
Google's Gemini 3 Pro Image Preview (a.k.a. Nano Banana Pro) to
recreate the scene with the model's face and identity.
"""

import os
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image


# Default prompt for scene recreation with identity transfer
DEFAULT_PROMPT = (
    "Reference: @Image1 (Scene/Pose), @Image2 (Identity)\n"
    "Goal: Recreate @Image1 exactly, but replace the person's face and "
    "identity with the individual from @Image2.\n"
    "Key Instructions:\n"
    "Maintain: Keep the exact outfit, pose, lighting, and background from @Image1.\n"
    "Transfer: Apply the face, hairstyle, and skin tone from @Image2 onto the subject.\n"
    "Clean: Ignore all text, watermarks, or UI elements from both images.\n"
    "Result: A seamless, photorealistic image where the person from @Image2 "
    "is the subject in @Image1's environment."
)

MODEL_ID = "gemini-3-pro-image-preview"
ASPECT_RATIO = "9:16"
RESOLUTION = "2K"


def recreate_scene(
    scene_image_path: str,
    model_image_path: str,
    output_path: Optional[str] = None,
    prompt: Optional[str] = None,
) -> str:
    """
    Recreate a scene with a different person's identity using Gemini.

    Args:
        scene_image_path: Path to the scene/pose reference image (@Image1).
        model_image_path: Path to the identity reference image (@Image2).
        output_path: Path for the output image. If None, defaults to
                     ``recreated_scene.png`` next to the scene image.
        prompt: Custom prompt. If None, uses DEFAULT_PROMPT.

    Returns:
        The path to the saved output image.

    Raises:
        FileNotFoundError: If either input image does not exist.
        EnvironmentError: If the GEMINI_API_KEY env var is not set.
        RuntimeError: If the API returns no image in its response.
    """
    # --- Validate inputs ---
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY environment variable is not set. "
            "Export it before calling this function."
        )

    if not os.path.isfile(scene_image_path):
        raise FileNotFoundError(f"Scene image not found: {scene_image_path}")

    if not os.path.isfile(model_image_path):
        raise FileNotFoundError(f"Model image not found: {model_image_path}")

    # --- Defaults ---
    if prompt is None:
        prompt = DEFAULT_PROMPT

    if output_path is None:
        out_dir = os.path.dirname(scene_image_path)
        output_path = os.path.join(out_dir, "recreated_scene.png")

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # --- Load images ---
    scene_image = Image.open(scene_image_path)
    model_image = Image.open(model_image_path)

    # --- Call Gemini API ---
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[
            prompt,
            scene_image,   # @Image1 — scene / pose reference
            model_image,   # @Image2 — identity reference
        ],
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=ASPECT_RATIO,
                image_size=RESOLUTION,
            ),
        ),
    )

    # --- Extract and save the generated image ---
    saved = False
    text_response = None

    for part in response.parts:
        if part.text is not None:
            text_response = part.text
        elif part.inline_data is not None:
            image = part.as_image()
            image.save(output_path)
            saved = True

    if not saved:
        detail = f" API text: {text_response}" if text_response else ""
        raise RuntimeError(
            f"Gemini returned no image in its response.{detail}"
        )

    return output_path
