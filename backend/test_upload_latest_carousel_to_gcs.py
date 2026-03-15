"""
Debug and upload helper for carousel->GCS integration.

What it does:
1) Prints effective env/config values (what this process sees)
2) Finds the latest non-empty folder under backend/carousel_images
3) Uploads PNGs to the target GCS bucket

Usage:
    cd backend
    export GOOGLE_APPLICATION_CREDENTIALS="/abs/path/service-account.json"
    export GCS_BUCKET_NAME="lumeet"
    python test_upload_latest_carousel_to_gcs.py

Optional:
    python test_upload_latest_carousel_to_gcs.py --bucket lumeet --prefix carousels/manual
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List

from google.cloud import storage

from config import GCS_BUCKET_NAME as CONFIG_GCS_BUCKET_NAME
from config import GCS_OBJECT_PREFIX as CONFIG_GCS_OBJECT_PREFIX


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload latest generated carousel images to GCS and print env/config resolution."
    )
    parser.add_argument(
        "--bucket",
        default="",
        help="Target bucket. Defaults to GCS_BUCKET_NAME env, then config, then 'lumeet'.",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="Object prefix. Defaults to GCS_OBJECT_PREFIX env/config.",
    )
    parser.add_argument(
        "--source-dir",
        default="",
        help="Optional explicit source folder. Defaults to latest folder in backend/carousel_images.",
    )
    return parser.parse_args()


def _sorted_pngs(folder: Path) -> List[Path]:
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".png"]

    def sort_key(path: Path):
        name = path.name
        if name == "hook.png":
            return (0, 0)
        if name.startswith("slide_"):
            num_part = name.replace("slide_", "").replace(".png", "")
            try:
                return (1, int(num_part))
            except ValueError:
                return (1, 9999)
        if name == "cta.png":
            return (2, 0)
        return (3, name)

    return sorted(files, key=sort_key)


def _latest_carousel_dir(base_dir: Path) -> Path:
    candidates = [d for d in base_dir.iterdir() if d.is_dir()]
    # folders are timestamped; lexical desc == latest
    for folder in sorted(candidates, key=lambda p: p.name, reverse=True):
        if _sorted_pngs(folder):
            return folder
    raise RuntimeError(f"No non-empty carousel folder found in {base_dir}")


def main() -> int:
    args = parse_args()
    backend_dir = Path(__file__).resolve().parent
    carousel_base = backend_dir / "carousel_images"

    env_bucket = os.environ.get("GCS_BUCKET_NAME", "").strip()
    env_prefix = os.environ.get("GCS_OBJECT_PREFIX", "").strip()
    creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

    bucket = (
        args.bucket.strip()
        or env_bucket
        or (CONFIG_GCS_BUCKET_NAME or "").strip()
        or "lumeet"
    )
    prefix = (
        args.prefix.strip()
        or env_prefix
        or (CONFIG_GCS_OBJECT_PREFIX or "").strip()
        or "carousels"
    ).strip("/")

    print("=== ENV / CONFIG DEBUG ===")
    print(f"os.environ GCS_BUCKET_NAME: {env_bucket or '<empty>'}")
    print(f"config.GCS_BUCKET_NAME: {CONFIG_GCS_BUCKET_NAME or '<empty>'}")
    print(f"effective bucket: {bucket}")
    print(f"os.environ GCS_OBJECT_PREFIX: {env_prefix or '<empty>'}")
    print(f"config.GCS_OBJECT_PREFIX: {CONFIG_GCS_OBJECT_PREFIX or '<empty>'}")
    print(f"effective prefix: {prefix}")
    print(
        "GOOGLE_APPLICATION_CREDENTIALS: "
        + (creds if creds else "<empty, using ADC>")
    )
    if creds:
        print(f"credentials file exists: {Path(creds).is_file()}")

    source_dir = Path(args.source_dir).resolve() if args.source_dir else _latest_carousel_dir(carousel_base)
    pngs = _sorted_pngs(source_dir)
    if not pngs:
        raise RuntimeError(f"No PNG files found in {source_dir}")

    print(f"\nLatest source folder: {source_dir}")
    print(f"Images to upload: {[p.name for p in pngs]}")

    client = storage.Client()
    bucket_ref = client.bucket(bucket)

    uploaded = []
    upload_prefix = f"{prefix}/{source_dir.name}"
    for img in pngs:
        object_name = f"{upload_prefix}/{img.name}"
        blob = bucket_ref.blob(object_name)
        blob.upload_from_filename(str(img), content_type="image/png")
        uploaded.append(f"gs://{bucket}/{object_name}")

    print("\n=== UPLOAD RESULT ===")
    for uri in uploaded:
        print(uri)
    print(f"\nSuccess: uploaded {len(uploaded)} image(s) to bucket '{bucket}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
