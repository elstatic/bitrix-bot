"""Синхронный Bitrix24 API клиент (stdlib only)."""

import json
import sys
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BitrixClient:
    """Синхронный клиент для Bitrix24 REST API."""

    def __init__(self, webhook_url: str, debug: bool = False):
        self.webhook_url = webhook_url.rstrip("/")
        self.debug = debug

    def _log(self, message: str):
        if self.debug:
            print(f"[BitrixClient] {message}", file=sys.stderr)

    def post(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Выполнить POST-запрос к API. Возвращает result или None."""
        url = f"{self.webhook_url}/{method}.json"
        payload = params or {}
        self._log(f"POST {method}")

        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(url, data=data, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError) as e:
            self._log(f"HTTP error: {e}")
            return None
        except Exception as e:
            self._log(f"Unexpected error: {e}")
            return None

        if "error" in body:
            self._log(f"API error: {body['error']} — {body.get('error_description', '')}")
            return body  # вернуть с ошибкой, чтобы caller мог проверить
        return body.get("result")

    def batch(self, commands: Dict[str, str]) -> Dict[str, Any]:
        """Выполнить batch запрос (до 50 команд). Возвращает {key: result}."""
        if len(commands) > 50:
            raise ValueError(f"Batch до 50 команд, передано: {len(commands)}")

        self._log(f"BATCH ({len(commands)} commands)")
        url = f"{self.webhook_url}/batch.json"
        payload = {"halt": 0, "cmd": commands}

        try:
            data = json.dumps(payload).encode("utf-8")
            req = Request(url, data=data, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError) as e:
            self._log(f"HTTP error: {e}")
            return {}
        except Exception as e:
            self._log(f"Unexpected error: {e}")
            return {}

        if "result" not in body:
            self._log(f"Batch error: {body}")
            return {}

        result = body["result"].get("result", {})
        result_error = body["result"].get("result_error", {})
        if isinstance(result_error, dict):
            for key, err in result_error.items():
                self._log(f"Error in '{key}': {err}")
        return result
