"""Configuration loader for department review."""

import os
from pathlib import Path


def _load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[len("export ") :]

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Config:
    """Runtime configuration."""

    def __init__(self, webhook_url: str):
        self.bitrix_webhook_url = (webhook_url or "").strip()
        if not self.bitrix_webhook_url:
            raise ValueError("BITRIX24_WEBHOOK_URL не задан в .env")


def load_config() -> Config:
    """Load .env from project root, then construct Config."""
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent.parent
    _load_dotenv(project_root / ".env")
    return Config(os.getenv("BITRIX24_WEBHOOK_URL", ""))

