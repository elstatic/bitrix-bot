"""Форматирование данных проекта в JSON для stdout."""

import json
from dataclasses import asdict
from typing import Any

from models import ProjectOverviewData


def format_json(data: ProjectOverviewData) -> str:
    """Форматировать данные обзора проекта в JSON."""
    output = {
        "project": {
            "name": data.project.name,
            "counter_id": data.project.counter_id,
            "group_id": data.project.group_id,
        },
        "period": {
            "from": data.period_from,
            "to": data.period_to,
        },
        "metrica": {
            "summary": asdict(data.metrica.summary),
            "trend": asdict(data.metrica.trend),
            "sources": [asdict(s) for s in data.metrica.sources],
            "goals": [asdict(g) for g in data.metrica.goals],
        },
        "bitrix": {
            "tasks_active_count": data.bitrix.tasks_active_count,
            "tasks_by_status": data.bitrix.tasks_by_status,
            "tasks_overdue": [asdict(t) for t in data.bitrix.tasks_overdue],
            "tasks_recently_completed": [asdict(t) for t in data.bitrix.tasks_recently_completed],
        },
    }

    if data.errors:
        output["errors"] = data.errors

    return json.dumps(output, ensure_ascii=False, indent=2)
