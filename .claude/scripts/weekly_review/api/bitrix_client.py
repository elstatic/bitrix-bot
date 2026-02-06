"""Async Bitrix24 API клиент с поддержкой batch запросов."""

import asyncio
import sys
from typing import Dict, Any, List, Optional
import aiohttp


class BitrixClient:
    """Асинхронный клиент для Bitrix24 API."""

    def __init__(self, webhook_url: str, debug: bool = False):
        """
        Инициализация клиента.

        Args:
            webhook_url: URL вебхука Bitrix24
            debug: Включить отладочный вывод
        """
        self.webhook_url = webhook_url.rstrip("/")
        self.debug = debug
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Создать сессию при входе в контекст."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрыть сессию при выходе из контекста."""
        if self.session:
            await self.session.close()

    def _log(self, message: str):
        """Вывести отладочное сообщение."""
        if self.debug:
            print(f"[BitrixClient] {message}", file=sys.stderr)

    async def batch(self, commands: Dict[str, str]) -> Dict[str, Any]:
        """
        Выполнить batch запрос (до 50 команд за раз).

        Args:
            commands: Словарь {key: api_method_with_params}

        Returns:
            Словарь {key: result}
        """
        if not self.session:
            raise RuntimeError("Сессия не инициализирована. Используйте async with.")

        if len(commands) > 50:
            raise ValueError(f"Batch поддерживает до 50 команд, передано: {len(commands)}")

        self._log(f"Выполняю batch запрос с {len(commands)} командами")

        url = f"{self.webhook_url}/batch.json"
        payload = {
            "halt": 0,  # Не останавливаться при ошибках
            "cmd": commands,
        }

        try:
            async with self.session.post(url, json=payload) as response:
                response.raise_for_status()
                data = await response.json()

                if "result" not in data:
                    self._log(f"Ошибка batch запроса: {data}")
                    return {}

                result = data["result"]["result"]

                # Проверить ошибки в отдельных командах
                for key, value in result.items():
                    if isinstance(value, dict) and "error" in value:
                        self._log(f"Ошибка в команде {key}: {value['error']}")

                return result

        except aiohttp.ClientError as e:
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
        if not self.session:
            raise RuntimeError("Сессия не инициализирована. Используйте async with.")

        url = f"{self.webhook_url}/{method}.json"
        params = params or {}

        self._log(f"Вызов {method}")

        try:
            async with self.session.post(url, json=params) as response:
                response.raise_for_status()
                data = await response.json()

                if "result" in data:
                    return data["result"]
                else:
                    self._log(f"Ошибка API: {data}")
                    return None

        except aiohttp.ClientError as e:
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

            # Для разных методов структура ответа может отличаться
            if isinstance(data, dict):
                items = data.get("tasks", data.get("result", []))
            elif isinstance(data, list):
                items = data
            else:
                break

            if not items:
                break

            results.extend(items)

            # Проверить, есть ли ещё страницы
            if isinstance(data, dict) and data.get("next"):
                start = data["next"]
            else:
                break

        self._log(f"Загружено {len(results)} записей из {method}")
        return results
