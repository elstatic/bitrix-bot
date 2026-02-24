"""Chat metrics collector (DM + shared group chats)."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Set, Tuple

from api.bitrix_client import BitrixClient
from models import ChatMetrics
from utils import parse_bitrix_datetime


def _is_in_period(raw: str | None, date_from: datetime, date_to: datetime) -> bool:
    dt = parse_bitrix_datetime(raw)
    if not dt:
        return False
    return date_from <= dt <= date_to


def _load_recent_dialogs(client: BitrixClient, chat_limit: int) -> Tuple[List[Dict], List[str]]:
    items: List[Dict] = []
    warnings: List[str] = []
    seen_ids: Set[str] = set()
    last_message_date: str | None = None

    while len(items) < chat_limit:
        params: Dict[str, object] = {"SKIP_OPENLINES": "Y"}
        if last_message_date:
            params["LAST_MESSAGE_DATE"] = last_message_date

        body = client.call_full("im.recent.list", params)
        if "error" in body:
            warnings.append(
                f"im.recent.list error: {body.get('error_description') or body.get('error')}"
            )
            break

        result = body.get("result", {})
        page_items = result.get("items", []) if isinstance(result, dict) else []
        if not page_items:
            break

        added = 0
        for item in page_items:
            dialog_id = str(item.get("id", "")).strip()
            if not dialog_id or dialog_id in seen_ids:
                continue
            seen_ids.add(dialog_id)
            items.append(item)
            added += 1
            if len(items) >= chat_limit:
                break

        last = page_items[-1] if page_items else {}
        next_date = last.get("date_message") or last.get("DATE_MESSAGE")
        if not next_date or added == 0:
            break
        last_message_date = str(next_date)

    return items, warnings


def _fetch_dialog_messages(
    client: BitrixClient,
    dialog_id: str,
    date_from: datetime,
    date_to: datetime,
    max_pages: int = 5,
    max_pages_when_empty: int = 3,
) -> Tuple[List[Dict], List[str]]:
    warnings: List[str] = []
    messages_in_period: List[Dict] = []
    pages = 0
    last_id: int | str | None = None
    first_page_all_in_period = False

    while pages < max_pages:
        params: Dict[str, object] = {"DIALOG_ID": dialog_id, "LIMIT": 20}
        if last_id:
            params["LAST_ID"] = last_id

        body = client.call_full("im.dialog.messages.get", params)
        if "error" in body:
            warnings.append(
                f"im.dialog.messages.get({dialog_id}) error: "
                f"{body.get('error_description') or body.get('error')}"
            )
            break

        result = body.get("result")
        if not isinstance(result, dict):
            break
        msgs = result.get("messages", [])
        if not msgs:
            break

        page_has_messages_in_period = False
        all_in_period = True
        for msg in msgs:
            raw_date = msg.get("date")
            if _is_in_period(raw_date, date_from, date_to):
                page_has_messages_in_period = True
                messages_in_period.append(msg)
            else:
                all_in_period = False

        if pages == 0 and not page_has_messages_in_period:
            last_id = msgs[-1].get("id")
            pages += 1
            if pages >= max_pages_when_empty:
                break
            continue

        if pages == 0 and all_in_period:
            first_page_all_in_period = True

        if first_page_all_in_period and pages + 1 < max_pages:
            last_id = msgs[-1].get("id")
            pages += 1
            continue

        break

    return messages_in_period, warnings


def collect_chat_metrics(
    client: BitrixClient,
    employee_ids: Set[str],
    date_from: datetime,
    date_to: datetime,
    chat_limit: int = 300,
    max_pages: int = 5,
) -> Tuple[Dict[str, ChatMetrics], List[str]]:
    """
    Collect chat metrics per employee.

    - DM metrics: messages in personal dialog employee<->manager.
    - Shared chat metrics: employee-authored messages in group chats visible to manager.
    """
    metrics = {employee_id: ChatMetrics() for employee_id in employee_ids}
    dialogs, warnings = _load_recent_dialogs(client, chat_limit=chat_limit)

    for dialog in dialogs:
        dialog_type = str(dialog.get("type", "")).lower()
        dialog_id = str(dialog.get("id", "")).strip()
        if not dialog_id:
            continue
        if dialog_type == "notification":
            continue

        # Personal dialog with employee.
        if dialog_type == "user" and dialog_id in employee_ids:
            messages, message_warnings = _fetch_dialog_messages(
                client,
                dialog_id=dialog_id,
                date_from=date_from,
                date_to=date_to,
                max_pages=max_pages,
            )
            warnings.extend(message_warnings)
            if messages:
                metrics[dialog_id].dm_dialogs += 1
                metrics[dialog_id].dm_messages += len(messages)
            continue

        # Group chat visible to manager: count employee-authored messages.
        if dialog_type == "chat" and dialog_id.startswith("chat"):
            messages, message_warnings = _fetch_dialog_messages(
                client,
                dialog_id=dialog_id,
                date_from=date_from,
                date_to=date_to,
                max_pages=max_pages,
            )
            warnings.extend(message_warnings)
            if not messages:
                continue

            per_employee_counts: Dict[str, int] = {}
            for msg in messages:
                author_id = str(msg.get("author_id", ""))
                if author_id in employee_ids:
                    per_employee_counts[author_id] = per_employee_counts.get(author_id, 0) + 1

            for employee_id, count in per_employee_counts.items():
                metrics[employee_id].shared_chat_dialogs += 1
                metrics[employee_id].shared_chat_messages += count

    return metrics, warnings

