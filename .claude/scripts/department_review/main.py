#!/usr/bin/env python3
"""Department review report for manager's subordinates."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Make script-local modules importable when launched as a plain file.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from api.bitrix_client import BitrixClient
from collectors.chats import collect_chat_metrics
from collectors.meetings import collect_employee_meetings_count
from collectors.tasks import collect_employee_task_metrics
from config import load_config
from formatters.markdown import format_report
from models import DepartmentInfo, DepartmentReport, EmployeeMetrics
from utils import normalize_department_ids, parse_id_list, parse_ymd


def _full_name(user: Dict[str, Any]) -> str:
    first = str(user.get("NAME", "")).strip()
    last = str(user.get("LAST_NAME", "")).strip()
    full = f"{first} {last}".strip()
    return full or f"ID {user.get('ID', '')}".strip()


def _parse_webhook_user_id(webhook_url: str) -> str:
    match = re.search(r"/rest/(\d+)/", webhook_url + "/")
    return match.group(1) if match else ""


def _get_manager_profile(client: BitrixClient, webhook_url: str) -> Tuple[str, str]:
    profile = client.call("profile")
    if isinstance(profile, dict):
        user_id = str(profile.get("ID", "")).strip()
        user_name = _full_name(profile)
        if user_id:
            return user_id, user_name

    profile = client.call("user.current")
    if isinstance(profile, dict):
        user_id = str(profile.get("ID", "")).strip()
        user_name = _full_name(profile)
        if user_id:
            return user_id, user_name

    fallback_id = _parse_webhook_user_id(webhook_url)
    return fallback_id, f"User {fallback_id}" if fallback_id else "Неизвестный"


def _load_departments(client: BitrixClient) -> List[DepartmentInfo]:
    body = client.call_full("department.get", {})
    if "error" in body:
        return []

    result = body.get("result")
    departments_raw: List[Dict[str, Any]] = []
    if isinstance(result, list):
        departments_raw = [item for item in result if isinstance(item, dict)]
    elif isinstance(result, dict):
        for key in ("departments", "items", "result"):
            value = result.get(key)
            if isinstance(value, list):
                departments_raw = [item for item in value if isinstance(item, dict)]
                break

    departments: List[DepartmentInfo] = []
    for item in departments_raw:
        dep_id = str(item.get("ID", "")).strip()
        dep_name = str(item.get("NAME", "")).strip() or str(item.get("name", "")).strip()
        if dep_id and dep_name:
            departments.append(DepartmentInfo(id=dep_id, name=dep_name))
    return departments


def _load_active_users(client: BitrixClient) -> List[Dict[str, Any]]:
    users: List[Dict[str, Any]] = []
    start = 0
    max_pages = 100
    pages = 0

    while pages < max_pages:
        params = {
            "FILTER": {"ACTIVE": "Y"},
            "SELECT": [
                "ID",
                "NAME",
                "LAST_NAME",
                "WORK_POSITION",
                "UF_DEPARTMENT",
                "PERSONAL_DEPARTMENT",
                "ACTIVE",
            ],
            "start": start,
        }
        body = client.call_full("user.get", params)
        if "error" in body:
            break

        result = body.get("result")
        page_users = result if isinstance(result, list) else []
        if not page_users:
            break

        users.extend([user for user in page_users if isinstance(user, dict)])
        next_start = body.get("next")
        if not isinstance(next_start, int):
            break
        start = next_start
        pages += 1

    return users


def _match_department(
    department_arg: str | None,
    department_id_arg: str | None,
    departments: List[DepartmentInfo],
    users: List[Dict[str, Any]],
) -> Tuple[DepartmentInfo | None, List[DepartmentInfo], str | None]:
    if department_id_arg:
        dep_id = department_id_arg.strip()
        for department in departments:
            if department.id == dep_id:
                return department, [], None
        # Unknown ID but still usable for filtering.
        return DepartmentInfo(id=dep_id, name=f"Отдел #{dep_id}"), [], None

    if not department_arg:
        return None, [], "Не указан отдел. Передайте --department или --department-id."

    query = department_arg.strip()
    if not query:
        return None, [], "Пустое значение отдела."

    if query.isdigit():
        dep_id = query
        for department in departments:
            if department.id == dep_id:
                return department, [], None
        return DepartmentInfo(id=dep_id, name=f"Отдел #{dep_id}"), [], None

    query_lower = query.lower()
    exact = [d for d in departments if d.name.lower() == query_lower]
    if len(exact) == 1:
        return exact[0], [], None
    if len(exact) > 1:
        return None, exact, None

    partial = [d for d in departments if query_lower in d.name.lower()]
    if len(partial) == 1:
        return partial[0], [], None
    if len(partial) > 1:
        return None, partial, None

    # Fallback: try PERSONAL_DEPARTMENT string on users to keep flow usable.
    for user in users:
        raw = str(user.get("PERSONAL_DEPARTMENT", "")).lower()
        if query_lower in raw and raw.strip():
            return DepartmentInfo(id="fallback-name", name=department_arg), [], None

    return None, [], f"Отдел по запросу '{department_arg}' не найден."


def _select_subordinates(
    users: List[Dict[str, Any]],
    manager_id: str,
    department: DepartmentInfo,
    include_ids: Set[str],
    exclude_ids: Set[str],
) -> List[Dict[str, Any]]:
    selected_by_id: Dict[str, Dict[str, Any]] = {}

    if department.id == "fallback-name":
        query_lower = department.name.lower()
        for user in users:
            dep_name = str(user.get("PERSONAL_DEPARTMENT", "")).strip().lower()
            user_id = str(user.get("ID", "")).strip()
            if user_id and query_lower in dep_name:
                selected_by_id[user_id] = user
    else:
        for user in users:
            user_id = str(user.get("ID", "")).strip()
            if not user_id:
                continue
            dep_ids = normalize_department_ids(user.get("UF_DEPARTMENT"))
            if department.id in dep_ids:
                selected_by_id[user_id] = user

    for include_id in include_ids:
        for user in users:
            if str(user.get("ID", "")).strip() == include_id:
                selected_by_id[include_id] = user
                break

    for excluded in exclude_ids:
        selected_by_id.pop(excluded, None)

    # Manager should not be treated as a subordinate.
    selected_by_id.pop(manager_id, None)

    return sorted(selected_by_id.values(), key=_full_name)


def _format_candidates_markdown(query: str, candidates: List[DepartmentInfo]) -> str:
    lines = [f"Найдено несколько отделов для «{query}». Уточните выбор по ID:"]
    for item in candidates:
        lines.append(f"- {item.id}: {item.name}")
    return "\n".join(lines)


def _format_candidates_json(candidates: List[DepartmentInfo], query: str) -> str:
    payload = {
        "needs_selection": True,
        "query": query,
        "department_candidates": [{"id": d.id, "name": d.name} for d in candidates],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_report(args: argparse.Namespace) -> Tuple[DepartmentReport | None, str | None, int]:
    config = load_config()
    client = BitrixClient(config.bitrix_webhook_url, debug=args.debug)

    date_from = parse_ymd(args.date_from, end_of_day=False)
    date_to = parse_ymd(args.date_to, end_of_day=True)

    if date_from > date_to:
        return None, "Дата начала больше даты окончания.", 2

    manager_id, manager_name = _get_manager_profile(client, config.bitrix_webhook_url)
    all_users = _load_active_users(client)
    departments = _load_departments(client)

    department, candidates, error = _match_department(
        department_arg=args.department,
        department_id_arg=args.department_id,
        departments=departments,
        users=all_users,
    )

    if candidates:
        if args.format == "json":
            return None, _format_candidates_json(candidates, args.department or ""), 4
        return None, _format_candidates_markdown(args.department or "", candidates), 4
    if error:
        return None, error, 2
    if department is None:
        return None, "Не удалось определить отдел.", 2

    include_ids = parse_id_list(args.include)
    exclude_ids = parse_id_list(args.exclude)

    selected_users = _select_subordinates(
        users=all_users,
        manager_id=manager_id,
        department=department,
        include_ids=include_ids,
        exclude_ids=exclude_ids,
    )

    report = DepartmentReport(
        manager_id=manager_id,
        manager_name=manager_name,
        department=department,
        date_from=date_from,
        date_to=date_to,
    )

    employees: List[EmployeeMetrics] = []
    for user in selected_users:
        employee = EmployeeMetrics(
            id=str(user.get("ID", "")),
            name=_full_name(user),
            work_position=str(user.get("WORK_POSITION", "")).strip(),
        )

        task_metrics, task_warnings = collect_employee_task_metrics(
            client=client,
            employee_id=employee.id,
            date_from=date_from,
            date_to=date_to,
        )
        employee.tasks = task_metrics
        employee.warnings.extend(task_warnings)

        meetings_count, meeting_warnings = collect_employee_meetings_count(
            client=client,
            employee_id=employee.id,
            date_from=date_from,
            date_to=date_to,
        )
        employee.meetings_count = meetings_count
        employee.warnings.extend(meeting_warnings)

        employees.append(employee)

    report.employees = employees

    if employees:
        employee_ids = {employee.id for employee in employees}
        chat_metrics, chat_warnings = collect_chat_metrics(
            client=client,
            employee_ids=employee_ids,
            date_from=date_from,
            date_to=date_to,
            chat_limit=args.chat_limit,
            max_pages=args.max_chat_pages,
        )
        report.warnings.extend(chat_warnings)
        for employee in report.employees:
            if employee.id in chat_metrics:
                employee.chats = chat_metrics[employee.id]

    if not report.employees:
        report.warnings.append("В выбранном отделе не найдено сотрудников (или все исключены).")

    return report, None, 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Отчёт по отделу и подчинённым")
    parser.add_argument("--department", help="Название отдела или ID")
    parser.add_argument("--department-id", help="Явный ID отдела")
    parser.add_argument("--from", dest="date_from", required=True, help="Дата начала (YYYY-MM-DD)")
    parser.add_argument("--to", dest="date_to", required=True, help="Дата окончания (YYYY-MM-DD)")
    parser.add_argument("--include", help="Дополнительно включить сотрудников по ID: 12,34")
    parser.add_argument("--exclude", help="Исключить сотрудников по ID: 56,78")
    parser.add_argument("--chat-limit", type=int, default=300, help="Лимит диалогов из im.recent.list")
    parser.add_argument("--max-chat-pages", type=int, default=5, help="Лимит страниц сообщений на диалог")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    try:
        report, message, code = build_report(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Критическая ошибка: {exc}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

    if report is None:
        if message:
            if args.format == "json":
                try:
                    parsed = json.loads(message)
                    print(json.dumps(parsed, ensure_ascii=False, indent=2))
                except Exception:
                    print(json.dumps({"error": message, "code": code}, ensure_ascii=False, indent=2))
            else:
                print(message)
        return code

    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
