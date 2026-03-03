"""Операции с Google Docs API."""

from googleapiclient.discovery import build

from auth import get_credentials


def _docs_service():
    return build("docs", "v1", credentials=get_credentials())


def _drive_service():
    return build("drive", "v3", credentials=get_credentials())


def _extract_text(doc: dict) -> str:
    """Извлечь текст из структуры Google Docs."""
    text_parts = []
    body = doc.get("body", {})
    for element in body.get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for elem in paragraph.get("elements", []):
            text_run = elem.get("textRun")
            if text_run:
                text_parts.append(text_run.get("content", ""))
    return "".join(text_parts)


def read(document_id: str) -> dict:
    """Прочитать текст документа."""
    svc = _docs_service()
    doc = svc.documents().get(documentId=document_id).execute()
    return {
        "title": doc.get("title", ""),
        "documentId": doc.get("documentId", ""),
        "text": _extract_text(doc),
    }


def create(title: str, folder_id: str = "") -> dict:
    """Создать новый документ."""
    drive_svc = _drive_service()
    metadata = {
        "name": title,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        metadata["parents"] = [folder_id]

    result = drive_svc.files().create(body=metadata, fields="id,name,webViewLink").execute()
    return {
        "documentId": result.get("id", ""),
        "title": result.get("name", ""),
        "webViewLink": result.get("webViewLink", ""),
    }
