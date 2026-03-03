"""Конфигурация: загрузка .env и пути к OAuth2 credentials."""

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


def get_project_root() -> Path:
    """Корень проекта (3 уровня вверх от .claude/scripts/google_workspace/)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def get_oauth_client_path() -> Path:
    """Путь к OAuth2 client credentials JSON."""
    root = get_project_root()
    _load_dotenv(str(root / ".env"))

    client_path = os.getenv("GOOGLE_OAUTH_CLIENT_PATH", "")
    if not client_path:
        raise FileNotFoundError(
            "GOOGLE_OAUTH_CLIENT_PATH не задан в .env. "
            'Добавьте: export GOOGLE_OAUTH_CLIENT_PATH=".claude/google-oauth-client.json"'
        )

    path = Path(client_path)
    if not path.is_absolute():
        path = root / path

    if not path.exists():
        raise FileNotFoundError(f"OAuth client файл не найден: {path}")

    return path


def get_oauth_token_path() -> Path:
    """Путь к кешированному OAuth2 токену (рядом с client credentials)."""
    client_path = get_oauth_client_path()
    return client_path.parent / "google-oauth-token.json"


# Скоупы для всех API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/script.projects",
]
