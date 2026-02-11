"""Конфигурация из переменных окружения."""

import os
from pathlib import Path
from typing import Optional


def _load_dotenv(env_path: str):
    """Загрузить .env файл в os.environ (без python-dotenv)."""
    path = Path(env_path)
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ")
        if "=" in line:
            key, _, value = line.partition("=")
            value = value.strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


class Config:
    """Конфигурация приложения."""

    def __init__(self):
        """Загрузить конфигурацию из .env."""
        self.bitrix_webhook_url: str = os.getenv("BITRIX24_WEBHOOK_URL", "")
        self.projects_dirs: str = os.getenv("PROJECTS_DIRS", "")

        # Валидация обязательных параметров
        if not self.bitrix_webhook_url:
            raise ValueError("BITRIX24_WEBHOOK_URL не задан в .env")

        # Развернуть тильду в путях (если задано)
        if self.projects_dirs:
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
    # Попробовать загрузить .env из корня проекта (fallback, если source .env не был вызван)
    script_dir = Path(__file__).resolve().parent
    # .claude/scripts/weekly_review/ -> корень проекта (3 уровня вверх)
    project_root = script_dir.parent.parent.parent
    _load_dotenv(str(project_root / ".env"))

    return Config()
