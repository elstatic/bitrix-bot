"""Sync Bitrix24 client with full-response access."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BitrixClient:
    """Minimal sync API client for Bitrix24 REST."""

    def __init__(self, webhook_url: str, debug: bool = False, timeout: int = 30):
        self.webhook_url = webhook_url.rstrip("/")
        self.debug = debug
        self.timeout = timeout

    def _log(self, message: str) -> None:
        if self.debug:
            print(f"[DepartmentReview/Bitrix] {message}", file=sys.stderr)

    def call_full(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call method and return full API body."""
        url = f"{self.webhook_url}/{method}.json"
        payload = params or {}

        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(url, data=data, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                if isinstance(body, dict):
                    return body
                return {"result": body}
        except HTTPError as exc:
            text = ""
            try:
                text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return {
                "error": "HTTP_ERROR",
                "error_description": f"{exc.code}: {text or str(exc)}",
            }
        except URLError as exc:
            return {
                "error": "NETWORK_ERROR",
                "error_description": str(exc),
            }
        except Exception as exc:
            return {
                "error": "UNEXPECTED_ERROR",
                "error_description": str(exc),
            }

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Call method and return `result` only."""
        body = self.call_full(method, params)
        if "error" in body:
            self._log(f"{method} failed: {body.get('error')} {body.get('error_description', '')}")
            return None
        return body.get("result")

