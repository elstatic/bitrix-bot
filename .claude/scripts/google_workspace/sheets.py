"""Операции с Google Sheets API."""

import json

from googleapiclient.discovery import build

from auth import get_credentials


def _service():
    return build("sheets", "v4", credentials=get_credentials())


def read(spreadsheet_id: str, range_: str = "") -> dict:
    """Прочитать данные из таблицы."""
    svc = _service()
    if range_:
        result = svc.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_
        ).execute()
    else:
        # Без range — читаем метаданные, затем первый лист целиком
        meta = svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        first_sheet = meta["sheets"][0]["properties"]["title"]
        result = svc.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=first_sheet
        ).execute()
    return {
        "range": result.get("range", ""),
        "values": result.get("values", []),
    }


def write(spreadsheet_id: str, range_: str, data_json: str) -> dict:
    """Записать данные в таблицу."""
    values = json.loads(data_json)
    svc = _service()
    body = {"values": values}
    result = svc.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_,
        valueInputOption="USER_ENTERED",
        body=body,
    ).execute()
    return {
        "updatedRange": result.get("updatedRange", ""),
        "updatedRows": result.get("updatedRows", 0),
        "updatedColumns": result.get("updatedColumns", 0),
        "updatedCells": result.get("updatedCells", 0),
    }


def info(spreadsheet_id: str) -> dict:
    """Метаданные таблицы: листы, размеры."""
    svc = _service()
    meta = svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = []
    for s in meta.get("sheets", []):
        props = s["properties"]
        grid = props.get("gridProperties", {})
        sheets.append({
            "title": props["title"],
            "sheetId": props["sheetId"],
            "rows": grid.get("rowCount", 0),
            "columns": grid.get("columnCount", 0),
        })
    return {
        "title": meta.get("properties", {}).get("title", ""),
        "spreadsheetId": meta.get("spreadsheetId", ""),
        "sheets": sheets,
    }
