"""Сбор задач Bitrix24 по группе проекта."""

import sys
from datetime import datetime, timedelta
from typing import Dict, Any, List

from api.bitrix_client import BitrixClient
from api.batch_builder import BatchRequestBuilder
from models import BitrixTask, BitrixData


# Статусы задач Bitrix24
STATUS_MAP = {
    "2": "Ждёт",
    "3": "В работе",
    "4": "На контроле",
    "5": "Завершена",
    "6": "Отложена",
}


def _parse_task(raw: Dict[str, Any]) -> BitrixTask:
    """Парсинг задачи из API ответа."""
    return BitrixTask(
        id=str(raw.get("id", raw.get("ID", ""))),
        title=raw.get("title", raw.get("TITLE", "")),
        status=str(raw.get("status", raw.get("STATUS", ""))),
        responsible_id=str(raw.get("responsibleId", raw.get("RESPONSIBLE_ID", ""))),
        creator_id=str(raw.get("creatorId", raw.get("CREATOR_ID", ""))),
        deadline=raw.get("deadline", raw.get("DEADLINE", "")),
        closed_date=raw.get("closedDate", raw.get("CLOSED_DATE", "")),
    )


class TasksAnalyzer:
    """Сбор задач по группе проекта в Битрикс24."""

    def __init__(self, bitrix: BitrixClient, debug: bool = False):
        self.bitrix = bitrix
        self.debug = debug

    def _log(self, message: str):
        if self.debug:
            print(f"[TasksAnalyzer] {message}", file=sys.stderr)

    async def collect(self, group_id: str) -> BitrixData:
        """Собрать задачи по группе: активные, просроченные, завершённые за 7 дней."""
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%dT%H:%M:%S")
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")

        builder = BatchRequestBuilder()

        # Активные задачи (не завершённые)
        builder.add_task_list("active", {
            "GROUP_ID": group_id,
            "!STATUS": "5",
        })

        # Просроченные задачи
        builder.add_task_list("overdue", {
            "GROUP_ID": group_id,
            "!STATUS": "5",
            "<DEADLINE": now_str,
        })

        # Завершённые за последние 7 дней
        builder.add_task_list("completed", {
            "GROUP_ID": group_id,
            "STATUS": "5",
            ">=CLOSED_DATE": week_ago,
        })

        self._log(f"Загрузка задач для группы {group_id}")
        result = await self.bitrix.batch(builder.build())

        # Парсинг результатов
        active_raw = result.get("active", {})
        overdue_raw = result.get("overdue", {})
        completed_raw = result.get("completed", {})

        # batch возвращает {"tasks": [...]} для tasks.task.list
        active_tasks = [_parse_task(t) for t in _extract_tasks(active_raw)]
        overdue_tasks = [_parse_task(t) for t in _extract_tasks(overdue_raw)]
        completed_tasks = [_parse_task(t) for t in _extract_tasks(completed_raw)]

        # Подсчёт по статусам
        status_counts: Dict[str, int] = {}
        for task in active_tasks:
            status_counts[task.status] = status_counts.get(task.status, 0) + 1

        self._log(
            f"Задачи: {len(active_tasks)} активных, "
            f"{len(overdue_tasks)} просроченных, "
            f"{len(completed_tasks)} завершённых"
        )

        return BitrixData(
            tasks_active_count=len(active_tasks),
            tasks_by_status=status_counts,
            tasks_overdue=overdue_tasks,
            tasks_recently_completed=completed_tasks,
        )


def _extract_tasks(raw: Any) -> list:
    """Извлечь список задач из ответа API."""
    if isinstance(raw, dict):
        return raw.get("tasks", [])
    if isinstance(raw, list):
        return raw
    return []
