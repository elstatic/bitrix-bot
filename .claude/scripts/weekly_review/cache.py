"""Утилиты для работы с кешем."""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Any


class Cache:
    """Простой файловый кеш с TTL."""

    def __init__(self, cache_file: Path, ttl_seconds: int = 86400):
        """
        Инициализация кеша.

        Args:
            cache_file: Путь к файлу кеша
            ttl_seconds: Время жизни кеша в секундах (по умолчанию 24 часа)
        """
        self.cache_file = cache_file
        self.ttl_seconds = ttl_seconds

    def get(self) -> Optional[Any]:
        """
        Получить данные из кеша.

        Returns:
            Данные или None если кеш устарел или не существует
        """
        if not self.cache_file.exists():
            return None

        try:
            cache_data = json.loads(self.cache_file.read_text())
            cache_time = datetime.fromisoformat(cache_data["timestamp"])
            cache_age = (datetime.now() - cache_time).total_seconds()

            if cache_age < self.ttl_seconds:
                return cache_data["data"]
        except Exception:
            pass

        return None

    def set(self, data: Any) -> None:
        """
        Сохранить данные в кеш.

        Args:
            data: Данные для кеширования
        """
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "data": data,
            }
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(cache_data, indent=2))
        except Exception:
            pass

    def clear(self) -> None:
        """Очистить кеш."""
        if self.cache_file.exists():
            self.cache_file.unlink()
