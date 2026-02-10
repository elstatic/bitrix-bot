"""Конфигурация из переменных окружения."""

import os
from pathlib import Path


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
        self.bitrix_webhook_url: str = os.getenv("BITRIX24_WEBHOOK_URL", "")
        self.yandex_metrica_token: str = os.getenv("YANDEX_METRICA_TOKEN", "")

        if not self.bitrix_webhook_url:
            raise ValueError("BITRIX24_WEBHOOK_URL не задан в .env")

        # yandex_metrica_token может быть пустым — Метрика будет пропущена


def load_config() -> Config:
    """Загрузить конфигурацию."""
    script_dir = Path(__file__).resolve().parent
    # .claude/scripts/project_overview/ -> корень проекта (3 уровня вверх)
    project_root = script_dir.parent.parent.parent
    _load_dotenv(str(project_root / ".env"))
    return Config()
