#!/usr/bin/env python3
"""
Quick test script to generate ONLY the hook image for a given headline + style.

Usage:
    python backend/test_hook.py "How Harvard students ACTUALLY study:"
    python backend/test_hook.py "5 tips for better focus while studying 🧠" --style study_desk
    python backend/test_hook.py "my favourite study methods that give me STRAIGHT A's" --style study_girl
"""

import argparse
import os
import sys

# Add backend to path so we can import from carousel_generator
sys.path.insert(0, os.path.dirname(__file__))

from carousel_generator import (
    HOOK_STYLES,
    DEFAULT_HOOK_STYLE,
    _build_hook_prompt,
    _resolve_openai_api_key,
    _generate_single_image,
    IMAGE_SIZE,
)
from openai import OpenAI


def main():
    parser = argparse.ArgumentParser(description="Generate a single hook image for testing")
    parser.add_argument("headline", help="The exact hook headline text to render on the image")
    parser.add_argument(
        "--style",
        choices=list(HOOK_STYLES.keys()),
        default="study_girl",
        help=f"Hook image style (default: study_girl). Options: {', '.join(HOOK_STYLES.keys())}",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: backend/test_hook_output.png)",
    )
    args = parser.parse_args()

    # Resolve output path
    output_path = args.output or os.path.join(os.path.dirname(__file__), "test_hook_output.png")

    # Build the hook prompt
    hook_prompt = _build_hook_prompt(headline=args.headline, hook_style=args.style)

    print(f"🎨 Style: {args.style}")
    print(f"📝 Headline: {args.headline}")
    print(f"📁 Output: {output_path}")
    print(f"🖼️  Image size: {IMAGE_SIZE}")
    print()
    print("Generating hook image...")

    # Resolve API key & create client
    api_key = _resolve_openai_api_key(None)
    if not api_key:
        print("❌ Error: No OpenAI API key found. Set OPENAI_API_KEY env var or add to .env file.")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # Generate!
    _generate_single_image(client, hook_prompt, output_path)

    print(f"\n✅ Hook image saved to: {output_path}")
    print(f"   Open it with: open {output_path}")


if __name__ == "__main__":
    main()
