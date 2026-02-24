"""Meetings collector for per-employee metrics."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from api.bitrix_client import BitrixClient


def _extract_events(result: object) -> List[Dict]:
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        if isinstance(result.get("items"), list):
            return result["items"]
        if isinstance(result.get("events"), list):
            return result["events"]
    return []


def collect_employee_meetings_count(
    client: BitrixClient,
    employee_id: str,
    date_from: datetime,
    date_to: datetime,
) -> Tuple[int, List[str]]:
    """Collect number of meetings for one employee in period."""
    params = {
        "type": "user",
        "ownerId": employee_id,
        "from": date_from.strftime("%Y-%m-%d"),
        "to": date_to.strftime("%Y-%m-%d"),
    }

    body = client.call_full("calendar.event.get", params)
    if "error" in body:
        return 0, [f"calendar.event.get error: {body.get('error_description') or body.get('error')}"]

    events = _extract_events(body.get("result"))
    count = 0
    for event in events:
        status = str(event.get("MEETING_STATUS", "")).upper()
        if status and status not in {"Y", "Q"}:
            continue
        count += 1

    return count, []

