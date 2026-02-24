"""Utilities for parsing dates and ids."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, List, Set


def parse_ymd(value: str, end_of_day: bool = False) -> datetime:
    dt = datetime.strptime(value, "%Y-%m-%d")
    if end_of_day:
        return dt.replace(hour=23, minute=59, second=59, microsecond=0)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def bitrix_datetime(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_bitrix_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None

    value = raw.strip()
    value = value.replace("Z", "")
    # Keep only datetime part without timezone offset.
    value = re.sub(r"([+-]\d{2}:\d{2})$", "", value)

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def normalize_department_ids(raw: object) -> Set[str]:
    if raw is None:
        return set()
    if isinstance(raw, (int, float)):
        return {str(int(raw))}
    if isinstance(raw, str):
        parts = [item.strip() for item in raw.split(",") if item.strip()]
        return {part for part in parts}
    if isinstance(raw, Iterable):
        result = set()
        for item in raw:
            if item is None:
                continue
            result.add(str(item))
        return result
    return set()


def parse_id_list(raw: str | None) -> Set[str]:
    if not raw:
        return set()
    return {part.strip() for part in raw.split(",") if part.strip()}


def format_period(date_from: datetime, date_to: datetime) -> str:
    return f"{date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}"

