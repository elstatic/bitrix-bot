"""Авторизация через OAuth2 (реальный пользователь Google)."""

import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from config import SCOPES, get_oauth_client_path, get_oauth_token_path


def get_credentials() -> Credentials:
    """Получить авторизованные credentials.

    1. Если токен существует — загрузить, обновить при необходимости.
    2. Если токена нет — запустить OAuth flow через браузер.
    """
    token_path = get_oauth_token_path()
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
        return creds

    # Первый запуск — OAuth flow через браузер
    client_path = get_oauth_client_path()
    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json())
    return creds


def check_auth() -> dict:
    """Проверить авторизацию, вернуть информацию об аккаунте."""
    creds = get_credentials()

    # Получаем email через Drive API about (scope drive уже есть)
    from googleapiclient.discovery import build

    email = ""
    try:
        service = build("drive", "v3", credentials=creds)
        about = service.about().get(fields="user(emailAddress,displayName)").execute()
        user = about.get("user", {})
        email = user.get("emailAddress", "")
        display_name = user.get("displayName", "")
    except Exception:
        email = "(не удалось получить email)"
        display_name = ""

    return {
        "status": "ok",
        "type": "oauth2",
        "email": email,
        "display_name": display_name,
        "scopes": SCOPES,
    }
