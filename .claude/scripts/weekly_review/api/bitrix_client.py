"""Async Bitrix24 API клиент с поддержкой batch запросов (stdlib only)."""

import asyncio
import json
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

_executor = ThreadPoolExecutor(max_workers=4)


def _make_ssl_context() -> ssl.SSLContext:
    """Создать SSL-контекст с сертификатами (certifi → системные → без проверки)."""
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        return ctx
    except ImportError:
        pass
    # Fallback: стандартный контекст (работает если системные серты доступны)
    return ssl.create_default_context()


class BitrixClient:
    """Асинхронный клиент для Bitrix24 API (без внешних зависимостей)."""

    def __init__(self, webhook_url: str, debug: bool = False):
        """
        Инициализация клиента.

        Args:
            webhook_url: URL вебхука Bitrix24
            debug: Включить отладочный вывод
        """
        self.webhook_url = webhook_url.rstrip("/")
        self.debug = debug
        self._ssl_ctx = _make_ssl_context()

    async def __aenter__(self):
        """Вход в контекст (no-op, сессия не нужна)."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекста (no-op)."""
        pass

    def _log(self, message: str):
        """Вывести отладочное сообщение."""
        if self.debug:
            print(f"[BitrixClient] {message}", file=sys.stderr)

    def _sync_post(self, url: str, payload: dict) -> dict:
        """Синхронный POST-запрос — вызывается в executor."""
        data = json.dumps(payload).encode("utf-8")
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=30, context=self._ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))

    async def _async_post(self, url: str, payload: dict) -> dict:
        """Async обёртка над синхронным HTTP через ThreadPoolExecutor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._sync_post, url, payload)

    async def batch(self, commands: Dict[str, str]) -> Dict[str, Any]:
        """
        Выполнить batch запрос (до 50 команд за раз).

        Args:
            commands: Словарь {key: api_method_with_params}

        Returns:
            Словарь {key: result}
        """
        if len(commands) > 50:
            raise ValueError(f"Batch поддерживает до 50 команд, передано: {len(commands)}")

        self._log(f"Выполняю batch запрос с {len(commands)} командами")

        url = f"{self.webhook_url}/batch.json"
        payload = {
            "halt": 0,
            "cmd": commands,
        }

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
        """
        Выполнить одиночный API вызов.

        Args:
            method: Метод API (например, "user.current")
            params: Параметры запроса

        Returns:
            Результат запроса
        """
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

    async def paginated_call(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        max_pages: int = 5,
    ) -> List[Any]:
        """
        Выполнить API вызов с автоматической пагинацией.

        Args:
            method: Метод API
            params: Параметры запроса
            max_pages: Максимальное количество страниц

        Returns:
            Список всех результатов
        """
        params = params or {}
        results = []
        start = 0

        for page in range(max_pages):
            params["start"] = start
            data = await self.call(method, params)

            if not data:
                break

            if isinstance(data, dict):
                items = data.get("tasks", data.get("result", []))
            elif isinstance(data, list):
                items = data
            else:
                break

            if not items:
                break

            results.extend(items)

            if isinstance(data, dict) and data.get("next"):
                start = data["next"]
            else:
                break

        self._log(f"Загружено {len(results)} записей из {method}")
        return results
