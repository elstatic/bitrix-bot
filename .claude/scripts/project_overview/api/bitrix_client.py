"""Async Bitrix24 API клиент с поддержкой batch запросов (stdlib only)."""

import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

_executor = ThreadPoolExecutor(max_workers=4)


class BitrixClient:
    """Асинхронный клиент для Bitrix24 API (без внешних зависимостей)."""

    def __init__(self, webhook_url: str, debug: bool = False):
        self.webhook_url = webhook_url.rstrip("/")
        self.debug = debug

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _log(self, message: str):
        if self.debug:
            print(f"[BitrixClient] {message}", file=sys.stderr)

    def _sync_post(self, url: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    async def _async_post(self, url: str, payload: dict) -> dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._sync_post, url, payload)

    async def batch(self, commands: Dict[str, str]) -> Dict[str, Any]:
        if len(commands) > 50:
            raise ValueError(f"Batch поддерживает до 50 команд, передано: {len(commands)}")

        self._log(f"Выполняю batch запрос с {len(commands)} командами")

        url = f"{self.webhook_url}/batch.json"
        payload = {"halt": 0, "cmd": commands}

        try:
            data = await self._async_post(url, payload)
            if "result" not in data:
                self._log(f"Ошибка batch запроса: {data}")
                return {}
            result = data["result"]["result"]
            for key, value in result.items():
                if isinstance(value, dict) and "error" in value:
                    self._log(f"Ошибка в команде {key}: {value['error']}")
            return result
        except (URLError, HTTPError) as e:
            self._log(f"Ошибка HTTP запроса: {e}")
            return {}
        except Exception as e:
            self._log(f"Неожиданная ошибка: {e}")
            return {}

    async def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{self.webhook_url}/{method}.json"
        params = params or {}
        self._log(f"Вызов {method}")

        try:
            data = await self._async_post(url, params)
            if "result" in data:
                return data["result"]
            else:
                self._log(f"Ошибка API: {data}")
                return None
        except (URLError, HTTPError) as e:
            self._log(f"Ошибка HTTP запроса к {method}: {e}")
            return None
        except Exception as e:
            self._log(f"Неожиданная ошибка в {method}: {e}")
            return None

    async def call_raw(self, method: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Вызов API с возвратом полного ответа (включая next, total)."""
        url = f"{self.webhook_url}/{method}.json"
        params = params or {}
        self._log(f"Вызов {method} (raw)")

        try:
            data = await self._async_post(url, params)
            if "error" in data:
                self._log(f"Ошибка API: {data}")
                return None
            return data
        except (URLError, HTTPError) as e:
            self._log(f"Ошибка HTTP запроса к {method}: {e}")
            return None
        except Exception as e:
            self._log(f"Неожиданная ошибка в {method}: {e}")
            return None
