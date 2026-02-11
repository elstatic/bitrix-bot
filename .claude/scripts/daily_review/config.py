"""Конфигурация для Daily Review (из .env)."""

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
        self.projects_dirs: str = os.getenv("PROJECTS_DIRS", "")

        if not self.bitrix_webhook_url:
            raise ValueError("BITRIX24_WEBHOOK_URL не задан в .env")

        if self.projects_dirs:
            self.projects_dirs = os.path.expanduser(self.projects_dirs)

    @property
    def cache_dir(self) -> Path:
        cache_path = Path.home() / ".cache" / "daily-review"
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path

    @property
    def chat_cache_dir(self) -> Path:
        path = self.cache_dir / "chat-digest"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def projects_cache_file(self) -> Path:
        return self.cache_dir / "projects-cache.json"


def load_config() -> Config:
    """Загрузить конфигурацию."""
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    _load_dotenv(str(project_root / ".env"))

    return Config()
