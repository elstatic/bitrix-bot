"""Операции с Google Drive API."""

from googleapiclient.discovery import build

from auth import get_credentials


def _service():
    return build("drive", "v3", credentials=get_credentials())


def list_files(query: str = "", drive_id: str = "") -> dict:
    """Список файлов. Опционально: query (Drive API q) и drive_id (Shared Drive)."""
    svc = _service()
    params = {
        "pageSize": 100,
        "fields": "files(id,name,mimeType,modifiedTime,owners,parents)",
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
    }
    if query:
        params["q"] = query
    if drive_id:
        params["driveId"] = drive_id
        params["corpora"] = "drive"
    else:
        params["corpora"] = "allDrives"

    result = svc.files().list(**params).execute()
    return {"files": result.get("files", [])}


def search(query: str) -> dict:
    """Поиск файлов по имени (fullText или name contains)."""
    q = f"name contains '{query}'"
    return list_files(query=q)


def file_info(file_id: str) -> dict:
    """Метаданные файла."""
    svc = _service()
    result = svc.files().get(
        fileId=file_id,
        fields="id,name,mimeType,modifiedTime,createdTime,owners,parents,size,webViewLink",
        supportsAllDrives=True,
    ).execute()
    return result
