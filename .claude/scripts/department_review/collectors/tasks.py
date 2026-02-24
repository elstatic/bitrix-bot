"""Tasks collector for per-employee metrics."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from api.bitrix_client import BitrixClient
from models import TaskMetrics
from utils import bitrix_datetime


def _extract_tasks(result: object) -> List[Dict]:
    if isinstance(result, dict):
        tasks = result.get("tasks")
        if isinstance(tasks, list):
            return tasks
        if isinstance(result.get("result"), list):
            return result["result"]
        return []
    if isinstance(result, list):
        return result
    return []


def _next_pointer(body: Dict, result: object) -> int | None:
    if isinstance(body.get("next"), int):
        return body["next"]
    if isinstance(result, dict) and isinstance(result.get("next"), int):
        return result["next"]
    return None


def _count_tasks(client: BitrixClient, filters: Dict, max_pages: int = 50) -> Tuple[int, str | None]:
    count = 0
    start = 0
    pages = 0

    while pages < max_pages:
        params = {
            "filter": filters,
            "select": ["ID"],
            "start": start,
        }
        body = client.call_full("tasks.task.list", params)
        if "error" in body:
            return 0, f"tasks.task.list error: {body.get('error_description') or body.get('error')}"

        result = body.get("result")
        tasks = _extract_tasks(result)
        count += len(tasks)

        next_start = _next_pointer(body, result)
        if next_start is None:
            break
        start = next_start
        pages += 1

    return count, None


def collect_employee_task_metrics(
    client: BitrixClient,
    employee_id: str,
    date_from: datetime,
    date_to: datetime,
) -> Tuple[TaskMetrics, List[str]]:
    """Collect created/closed/overdue counts for one employee."""
    warnings: List[str] = []
    from_str = bitrix_datetime(date_from)
    to_str = bitrix_datetime(date_to)

    created_filters = {
        "CREATED_BY": employee_id,
        ">=CREATED_DATE": from_str,
        "<=CREATED_DATE": to_str,
    }
    created_count, error = _count_tasks(client, created_filters)
    if error:
        warnings.append(error)

    closed_filters = {
        "RESPONSIBLE_ID": employee_id,
        "STATUS": "5",
        ">=CLOSED_DATE": from_str,
        "<=CLOSED_DATE": to_str,
    }
    closed_count, error = _count_tasks(client, closed_filters)
    if error:
        warnings.append(error)

    overdue_filters = {
        "RESPONSIBLE_ID": employee_id,
        "!STATUS": "5",
        "<=DEADLINE": to_str,
    }
    overdue_count, error = _count_tasks(client, overdue_filters)
    if error:
        warnings.append(error)

    return (
        TaskMetrics(
            created=created_count,
            closed=closed_count,
            overdue=overdue_count,
        ),
        warnings,
    )

