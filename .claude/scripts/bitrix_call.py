#!/usr/bin/env python3
"""Simple Bitrix24 API caller using stdlib only.

Examples:
  python3 .claude/scripts/bitrix_call.py profile
  python3 .claude/scripts/bitrix_call.py im.recent.list --params '{"SKIP_OPENLINES":"Y"}'
  python3 .claude/scripts/bitrix_call.py im.dialog.messages.get --webhook "https://.../rest/ID/CODE/" --params '{"DIALOG_ID":"chat123","LIMIT":20}'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_params(raw_params: str, kv_params: list[str]) -> dict:
    params: dict = {}

    if raw_params.strip():
        loaded = json.loads(raw_params)
        if not isinstance(loaded, dict):
            raise ValueError("--params must be a JSON object")
        params.update(loaded)

    for item in kv_params:
        if "=" not in item:
            raise ValueError(f"Invalid --param value: {item}. Expected KEY=VALUE.")
        key, value_raw = item.split("=", 1)
        value = value_raw
        # Try to preserve numbers/booleans/null when possible.
        try:
            value = json.loads(value_raw)
        except Exception:
            pass
        params[key] = value

    return params


def main() -> int:
    parser = argparse.ArgumentParser(description="Call Bitrix24 API method")
    parser.add_argument("method", help="Bitrix API method, e.g. profile or im.recent.list")
    parser.add_argument(
        "--webhook",
        help="Full webhook URL (if omitted, BITRIX24_WEBHOOK_URL is used from env/.env)",
    )
    parser.add_argument(
        "--params",
        default="{}",
        help='JSON object with params, e.g. \'{"LIMIT":20}\'',
    )
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        help="Single KEY=VALUE param (can be repeated)",
    )
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args()

    load_dotenv(Path(".env"))

    webhook = (args.webhook or os.getenv("BITRIX24_WEBHOOK_URL", "")).strip().rstrip("/")
    if not webhook:
        print("BITRIX24_WEBHOOK_URL is not set (pass --webhook or configure .env)", file=sys.stderr)
        return 2

    method = args.method.strip()
    if method.endswith(".json"):
        method = method[:-5]

    try:
        payload = parse_params(args.params, args.param)
    except Exception as exc:
        print(f"Failed to parse params: {exc}", file=sys.stderr)
        return 2

    url = f"{webhook}/{method}.json"
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urlopen(req, timeout=args.timeout) as resp:
            body = resp.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        print(f"HTTP error {exc.code}: {body}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    try:
        parsed = json.loads(body)
    except Exception:
        print(body)
        return 0

    if "error" in parsed:
        print(json.dumps(parsed, ensure_ascii=False, indent=2 if args.pretty else None), file=sys.stderr)
        return 1

    result = parsed.get("result", parsed)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
