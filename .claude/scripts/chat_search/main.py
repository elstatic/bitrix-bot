#!/usr/bin/env python3
"""CLI для поиска чатов и сообщений Битрикс24."""

import argparse
import json
import sys
from datetime import datetime
from urllib.parse import quote

# Абсолютные импорты — main.py добавляет свою директорию в sys.path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from api import BitrixClient
from config import load_config


def find_chat(client: BitrixClient, query: str) -> list:
    """Поиск чатов и пользователей по имени."""
    query_lower = query.lower()

    # 1. Попробовать im.search через batch
    encoded_query = quote(query, safe="")
    results = client.batch({
        "chats": f"im.search.chat.list?FIND={encoded_query}",
        "users": f"im.search.user.list?FIND={encoded_query}",
    })

    found = []

    # Чаты
    chats = results.get("chats", [])
    if isinstance(chats, dict) and "error" in chats:
        chats = []
    if isinstance(chats, list):
        for c in chats:
            found.append({
                "id": c.get("id"),
                "dialog_id": f"chat{c['id']}",
                "title": c.get("name", ""),
                "type": "chat",
                "message_count": c.get("message_count", 0),
            })

    # Пользователи
    users = results.get("users", [])
    if isinstance(users, dict) and "error" in users:
        users = []
    if isinstance(users, list):
        for u in users:
            found.append({
                "id": u.get("id"),
                "dialog_id": str(u["id"]),
                "title": u.get("name", ""),
                "type": "user",
            })

    # Если нашли — вернуть
    if found:
        return found

    # 2. Фолбэк: im.recent.list + фильтрация по подстроке
    print(f"[fallback] im.search вернул пусто, ищу в im.recent.list...", file=sys.stderr)
    last_date = None
    for page in range(3):
        params = {"SKIP_OPENLINES": "Y"}
        if last_date:
            params["LAST_MESSAGE_DATE"] = last_date

        result = client.post("im.recent.list", params)
        if not result or "items" not in result:
            break

        items = result["items"]
        if not items:
            break

        for item in items:
            title = item.get("title", "")
            if query_lower in title.lower():
                dialog_id = str(item.get("id", ""))
                item_type = item.get("type", "")
                found.append({
                    "id": item.get("id"),
                    "dialog_id": dialog_id if item_type == "user" else dialog_id,
                    "title": title,
                    "type": item_type,
                    "last_message_date": item.get("date_message"),
                })

        last_date = items[-1].get("date_message")
        if not last_date:
            break

    return found


def get_messages(client: BitrixClient, dialog_id: str, limit: int = 50,
                 text: str = None, date_from: str = None, date_to: str = None) -> list:
    """Получить сообщения из диалога с фильтрацией."""
    messages = []
    users_map = {}
    last_id = None
    max_pages = 5
    per_page = 20

    # Парсинг дат фильтра
    dt_from = datetime.fromisoformat(date_from) if date_from else None
    dt_to = datetime.fromisoformat(date_to + "T23:59:59") if date_to else None

    for page in range(max_pages):
        params = {"DIALOG_ID": dialog_id, "LIMIT": per_page}
        if last_id:
            params["LAST_ID"] = last_id

        result = client.post("im.dialog.messages.get", params)
        if not result:
            break

        # Собрать карту пользователей
        for u in result.get("users", []):
            users_map[u["id"]] = u.get("name", f"user#{u['id']}")

        page_msgs = result.get("messages", [])
        if not page_msgs:
            break

        for m in page_msgs:
            msg_date = m.get("date", "")

            # Фильтр по дате
            if msg_date and (dt_from or dt_to):
                try:
                    md = datetime.fromisoformat(msg_date.replace("+00:00", "+00:00"))
                    if dt_from and md < dt_from:
                        continue
                    if dt_to and md > dt_to:
                        continue
                except (ValueError, TypeError):
                    pass

            # Фильтр по тексту
            msg_text = m.get("text", "")
            if text and text.lower() not in msg_text.lower():
                continue

            messages.append({
                "id": m.get("id"),
                "author": users_map.get(m.get("author_id"), f"user#{m.get('author_id')}"),
                "author_id": m.get("author_id"),
                "text": msg_text,
                "date": msg_date,
            })

            if len(messages) >= limit:
                break

        if len(messages) >= limit:
            break

        # Пагинация: LAST_ID = минимальный ID на странице
        ids = [m["id"] for m in page_msgs if m.get("id")]
        if ids:
            last_id = min(ids)
        else:
            break

    # Сортировка по дате (старые сверху)
    messages.sort(key=lambda m: m.get("date", ""))
    return messages[:limit]


def send_message(client: BitrixClient, dialog_id: str, message: str) -> dict:
    """Отправить сообщение в диалог."""
    result = client.post("im.message.add", {
        "DIALOG_ID": dialog_id,
        "MESSAGE": message,
    })
    if result and isinstance(result, (int, str)):
        return {"success": True, "message_id": result}
    if isinstance(result, dict) and "error" in result:
        return {"success": False, "error": result.get("error_description", result["error"])}
    return {"success": False, "error": "Unexpected response", "raw": result}


def main():
    parser = argparse.ArgumentParser(description="Поиск чатов и сообщений Битрикс24")
    parser.add_argument("--debug", action="store_true", help="Отладочный вывод")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # find-chat
    p_find = subparsers.add_parser("find-chat", help="Поиск чатов по имени")
    p_find.add_argument("query", help="Строка поиска")

    # messages
    p_msg = subparsers.add_parser("messages", help="Чтение сообщений из диалога")
    p_msg.add_argument("dialog_id", help="ID диалога (chatXXXXX или число)")
    p_msg.add_argument("--limit", type=int, default=50, help="Макс. сообщений (по умолчанию 50)")
    p_msg.add_argument("--text", help="Фильтр по тексту")
    p_msg.add_argument("--from", dest="date_from", help="Дата от (YYYY-MM-DD)")
    p_msg.add_argument("--to", dest="date_to", help="Дата до (YYYY-MM-DD)")

    # send
    p_send = subparsers.add_parser("send", help="Отправить сообщение")
    p_send.add_argument("dialog_id", help="ID диалога")
    p_send.add_argument("message", help="Текст сообщения")

    args = parser.parse_args()

    webhook_url = load_config()
    client = BitrixClient(webhook_url, debug=args.debug)

    if args.command == "find-chat":
        result = find_chat(client, args.query)
    elif args.command == "messages":
        result = get_messages(client, args.dialog_id, limit=args.limit,
                              text=args.text, date_from=args.date_from, date_to=args.date_to)
    elif args.command == "send":
        result = send_message(client, args.dialog_id, args.message)
    else:
        parser.print_help()
        sys.exit(1)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    main()
