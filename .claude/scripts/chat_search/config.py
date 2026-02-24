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


def load_config() -> str:
    """Загрузить BITRIX24_WEBHOOK_URL из .env и вернуть его."""
    script_dir = Path(__file__).resolve().parent
    # .claude/scripts/chat_search/ -> корень проекта (3 уровня вверх)
    project_root = script_dir.parent.parent.parent
    _load_dotenv(str(project_root / ".env"))

    url = os.getenv("BITRIX24_WEBHOOK_URL", "")
    if not url:
        raise ValueError("BITRIX24_WEBHOOK_URL не задан в .env")
    return url
