"""Конфигурация из переменных окружения."""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Конфигурация приложения."""

    def __init__(self):
        """Загрузить конфигурацию из .env."""
        self.bitrix_webhook_url: str = os.getenv("BITRIX24_WEBHOOK_URL", "")
        self.projects_dirs: str = os.getenv("PROJECTS_DIRS", "~/projects")

        # Валидация обязательных параметров
        if not self.bitrix_webhook_url:
            raise ValueError("BITRIX24_WEBHOOK_URL не задан в .env")

        # Развернуть тильду в путях
        self.projects_dirs = os.path.expanduser(self.projects_dirs)

    @property
    def cache_dir(self) -> Path:
        """Директория для кеша."""
        cache_path = Path.home() / ".cache" / "weekly-review"
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path

    @property
    def projects_cache_file(self) -> Path:
        """Файл кеша проектов."""
        return self.cache_dir / "projects-cache.json"


def load_config() -> Config:
    """Загрузить конфигурацию."""
    return Config()
