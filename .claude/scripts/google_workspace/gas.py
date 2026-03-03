"""Операции с Google Apps Script API."""

import json
import re
import ssl
import urllib.request
import urllib.error

from googleapiclient.discovery import build

from auth import get_credentials
from drive import list_files

try:
    import certifi
    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = ssl.create_default_context()


def _service():
    return build("script", "v1", credentials=get_credentials())


def get_project(script_id: str) -> dict:
    """Получить все файлы GAS-проекта."""
    svc = _service()
    content = svc.projects().getContent(scriptId=script_id).execute()
    files = []
    for f in content.get("files", []):
        files.append({
            "name": f.get("name", ""),
            "type": f.get("type", ""),
            "source": f.get("source", ""),
        })
    return {"scriptId": script_id, "files": files}


def update_project(script_id: str, files_json: str) -> dict:
    """Обновить файлы GAS-проекта."""
    files = json.loads(files_json)
    svc = _service()
    body = {"files": files}
    svc.projects().updateContent(scriptId=script_id, body=body).execute()
    return {"status": "ok", "scriptId": script_id, "filesUpdated": len(files)}


def list_projects() -> dict:
    """Список GAS-проектов (через Drive API по mimeType)."""
    result = list_files(query="mimeType='application/vnd.google-apps.script'")
    return result


def _parse_spreadsheet_id(url_or_id: str) -> str:
    """Извлечь spreadsheet ID из URL или вернуть как есть."""
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url_or_id)
    return m.group(1) if m else url_or_id


def find_bound_script(spreadsheet_url_or_id: str) -> dict:
    """Найти container-bound скрипт таблицы через HTML + редирект.

    1. Загружает HTML таблицы с OAuth-токеном
    2. Извлекает maestro_script_editor_uri
    3. Проходит по редиректу → получает scriptId из URL
    4. Возвращает метаданные и файлы проекта
    """
    creds = get_credentials()
    spreadsheet_id = _parse_spreadsheet_id(spreadsheet_url_or_id)

    # 1. Fetch spreadsheet HTML
    sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    req = urllib.request.Request(sheet_url, headers={
        "Authorization": f"Bearer {creds.token}",
    })
    with urllib.request.urlopen(req, context=_SSL_CTX) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    # 2. Extract maestro_script_editor_uri
    m = re.search(
        r'maestro_script_editor_uri["\s:]+https://script\.google\.com[^"\\]*(?:\\.[^"\\]*)*',
        html,
    )
    if not m:
        return {"error": "Bound-скрипт не найден в этой таблице", "spreadsheetId": spreadsheet_id}

    editor_url = m.group()
    # Извлекаем URL из значения
    url_m = re.search(r'(https://script\.google\.com\S+)', editor_url)
    if not url_m:
        return {"error": "Не удалось извлечь URL скрипт-редактора"}
    maestro_url = url_m.group(1).replace("\\u003d", "=").replace("\\u0026", "&").rstrip('"')

    # 3. Follow redirect to get scriptId
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            self.redirect_url = newurl
            return None

    handler = _NoRedirect()
    opener = urllib.request.build_opener(handler, urllib.request.HTTPSHandler(context=_SSL_CTX))
    redirect_req = urllib.request.Request(maestro_url, headers={
        "Authorization": f"Bearer {creds.token}",
    })
    try:
        opener.open(redirect_req)
    except urllib.error.HTTPError:
        pass

    redirect_url = getattr(handler, "redirect_url", "")
    script_m = re.search(r'/d/([a-zA-Z0-9_-]{20,})/', redirect_url)
    if not script_m:
        return {"error": "Не удалось получить scriptId из редиректа", "redirect_url": redirect_url}

    script_id = script_m.group(1)

    # 4. Get project metadata and content
    svc = _service()
    project = svc.projects().get(scriptId=script_id).execute()
    content = svc.projects().getContent(scriptId=script_id).execute()

    files = []
    for f in content.get("files", []):
        files.append({
            "name": f.get("name", ""),
            "type": f.get("type", ""),
            "source": f.get("source", ""),
        })

    return {
        "scriptId": script_id,
        "title": project.get("title", ""),
        "parentId": project.get("parentId", ""),
        "files": files,
    }
