"""
Simple manual connectivity test for Late API.

Usage:
    cd backend
    export LATE_API_KEY="sk_..."
    python test_late_connection.py

Optional:
    python test_late_connection.py --profile-id prof_abc123
    python test_late_connection.py --base-url https://getlate.dev/api/v1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Late API connection with GET /accounts.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("LATE_API_BASE_URL", "https://getlate.dev/api/v1"),
        help="Late API base URL.",
    )
    parser.add_argument(
        "--profile-id",
        default=None,
        help="Optional profileId filter for accounts.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Request timeout in seconds (default: 20).",
    )
    return parser.parse_args()


def _read_env_value(env_path: Path, key: str) -> str:
    if not env_path.is_file():
        return ""
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() != key:
            continue
        cleaned = value.strip().strip("'").strip('"')
        return cleaned
    return ""


def _resolve_api_key() -> str:
    key = os.environ.get("LATE_API_KEY", "").strip()
    if key:
        return key

    here = Path(__file__).resolve().parent
    candidates = [
        here / ".env",          # backend/.env
        here.parent / ".env",   # repo/.env
    ]
    for env_path in candidates:
        key = _read_env_value(env_path, "LATE_API_KEY")
        if key:
            return key
    return ""


def main() -> int:
    args = parse_args()
    api_key = _resolve_api_key()
    if not api_key:
        print("ERROR: LATE_API_KEY is not set.")
        print('Set it first, e.g. export LATE_API_KEY="sk_..."')
        print("Or add LATE_API_KEY to backend/.env or repo .env")
        return 1

    url = f"{args.base_url.rstrip('/')}/accounts"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {}
    if args.profile_id:
        params["profileId"] = args.profile_id

    query = urllib.parse.urlencode(params)
    final_url = f"{url}?{query}" if query else url

    print(f"Requesting: GET {final_url}")
    if params:
        print(f"Query params: {params}")

    request = urllib.request.Request(
        final_url,
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            status_code = response.status
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        print(f"Connection failed: {exc}")
        return 1

    print(f"Status: {status_code}")
    try:
        payload = json.loads(body)
    except ValueError:
        payload = {"raw": body}

    if status_code >= 400:
        print("Late API returned an error:")
        print(json.dumps(payload, indent=2))
        return 1

    accounts = payload.get("accounts", [])
    print(f"Success: received {len(accounts)} account(s)")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
