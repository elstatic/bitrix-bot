#!/usr/bin/env python3
"""CLI для работы с Google Workspace: Sheets, Drive, Docs, Apps Script."""

import argparse
import json
import sys
from pathlib import Path

# Добавить свою директорию в sys.path для абсолютных импортов
sys.path.insert(0, str(Path(__file__).resolve().parent))


def cmd_auth(_args):
    """Проверить авторизацию."""
    from auth import check_auth
    return check_auth()


def cmd_sheets_read(args):
    """Прочитать данные из таблицы."""
    from sheets import read
    return read(args.spreadsheet_id, args.range or "")


def cmd_sheets_write(args):
    """Записать данные в таблицу."""
    from sheets import write
    return write(args.spreadsheet_id, args.range, args.json_data)


def cmd_sheets_info(args):
    """Метаданные таблицы."""
    from sheets import info
    return info(args.spreadsheet_id)


def cmd_drive_list(args):
    """Список файлов на Drive."""
    from drive import list_files
    return list_files(query=args.query or "", drive_id=args.drive_id or "")


def cmd_drive_search(args):
    """Поиск файлов."""
    from drive import search
    return search(args.query)


def cmd_drive_info(args):
    """Метаданные файла."""
    from drive import file_info
    return file_info(args.file_id)


def cmd_docs_read(args):
    """Прочитать документ."""
    from docs import read
    return read(args.document_id)


def cmd_docs_create(args):
    """Создать документ."""
    from docs import create
    return create(args.title, folder_id=args.folder or "")


def cmd_gas_get(args):
    """Получить файлы GAS-проекта."""
    from gas import get_project
    return get_project(args.script_id)


def cmd_gas_update(args):
    """Обновить файлы GAS-проекта."""
    from gas import update_project
    return update_project(args.script_id, args.json_files)


def cmd_gas_list(_args):
    """Список GAS-проектов."""
    from gas import list_projects
    return list_projects()


def cmd_gas_bound(args):
    """Найти bound-скрипт таблицы."""
    from gas import find_bound_script
    return find_bound_script(args.spreadsheet_url)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Google Workspace CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # auth
    sub.add_parser("auth", help="Проверить авторизацию")

    # sheets
    sheets = sub.add_parser("sheets", help="Google Sheets")
    sheets_sub = sheets.add_subparsers(dest="sheets_cmd", required=True)

    sr = sheets_sub.add_parser("read", help="Прочитать данные")
    sr.add_argument("spreadsheet_id")
    sr.add_argument("range", nargs="?", default="")

    sw = sheets_sub.add_parser("write", help="Записать данные")
    sw.add_argument("spreadsheet_id")
    sw.add_argument("range")
    sw.add_argument("json_data", help='JSON-массив: [["a","b"],["c","d"]]')

    si = sheets_sub.add_parser("info", help="Метаданные таблицы")
    si.add_argument("spreadsheet_id")

    # drive
    drive = sub.add_parser("drive", help="Google Drive")
    drive_sub = drive.add_subparsers(dest="drive_cmd", required=True)

    dl = drive_sub.add_parser("list", help="Список файлов")
    dl.add_argument("--query", "-q", default="")
    dl.add_argument("--drive-id", default="")

    ds = drive_sub.add_parser("search", help="Поиск файлов")
    ds.add_argument("query")

    di = drive_sub.add_parser("info", help="Метаданные файла")
    di.add_argument("file_id")

    # docs
    docs = sub.add_parser("docs", help="Google Docs")
    docs_sub = docs.add_subparsers(dest="docs_cmd", required=True)

    dr = docs_sub.add_parser("read", help="Прочитать документ")
    dr.add_argument("document_id")

    dc = docs_sub.add_parser("create", help="Создать документ")
    dc.add_argument("title")
    dc.add_argument("--folder", default="")

    # gas
    gas = sub.add_parser("gas", help="Google Apps Script")
    gas_sub = gas.add_subparsers(dest="gas_cmd", required=True)

    gg = gas_sub.add_parser("get", help="Получить файлы проекта")
    gg.add_argument("script_id")

    gu = gas_sub.add_parser("update", help="Обновить файлы проекта")
    gu.add_argument("script_id")
    gu.add_argument("json_files", help="JSON с массивом файлов")

    gas_sub.add_parser("list", help="Список GAS-проектов")

    gb = gas_sub.add_parser("bound", help="Найти bound-скрипт таблицы")
    gb.add_argument("spreadsheet_url", help="URL или ID таблицы")

    return parser


HANDLERS = {
    ("auth", None): cmd_auth,
    ("sheets", "read"): cmd_sheets_read,
    ("sheets", "write"): cmd_sheets_write,
    ("sheets", "info"): cmd_sheets_info,
    ("drive", "list"): cmd_drive_list,
    ("drive", "search"): cmd_drive_search,
    ("drive", "info"): cmd_drive_info,
    ("docs", "read"): cmd_docs_read,
    ("docs", "create"): cmd_docs_create,
    ("gas", "get"): cmd_gas_get,
    ("gas", "update"): cmd_gas_update,
    ("gas", "list"): cmd_gas_list,
    ("gas", "bound"): cmd_gas_bound,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    cmd = args.command
    subcmd = None
    for attr in ("sheets_cmd", "drive_cmd", "docs_cmd", "gas_cmd"):
        val = getattr(args, attr, None)
        if val:
            subcmd = val
            break

    handler = HANDLERS.get((cmd, subcmd))
    if not handler:
        parser.print_help()
        sys.exit(1)

    try:
        result = handler(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
