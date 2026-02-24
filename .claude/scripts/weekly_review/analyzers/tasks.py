"""Анализатор задач и трудозатрат из Bitrix24."""

import sys
from datetime import datetime
from typing import List, Dict, Any

from api.bitrix_client import BitrixClient
from api.batch_builder import BatchRequestBuilder
from models import Task, TimeEntry
from date_utils import parse_bitrix_datetime, format_bitrix_date_filter


class TaskAnalyzer:
    """Анализ задач и трудозатрат."""

    def __init__(self, client: BitrixClient, user_id: str, debug: bool = False):
        self.client = client
        self.user_id = user_id
        self.debug = debug

    def _log(self, message: str):
        """Вывести отладочное сообщение."""
        if self.debug:
            print(f"[TaskAnalyzer] {message}", file=sys.stderr)

    async def collect_tasks(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> Dict[str, List[Task]]:
        """
        Собрать все задачи за период через batch запрос.

        Returns:
            Словарь с ключами: created, assigned, closed, active
        """
        self._log(f"Сбор задач за период {date_from} — {date_to}")

        from_str = format_bitrix_date_filter(date_from)
        to_str = format_bitrix_date_filter(date_to)

        # Построить batch запрос
        builder = BatchRequestBuilder()

        # Созданные задачи
        builder.add_task_list(
            "tasks_created",
            filters={
                "CREATED_BY": self.user_id,
                ">=CREATED_DATE": from_str,
                "<=CREATED_DATE": to_str,
            }
        )

        # Назначенные задачи
        builder.add_task_list(
            "tasks_assigned",
            filters={
                "RESPONSIBLE_ID": self.user_id,
                ">=CREATED_DATE": from_str,
                "<=CREATED_DATE": to_str,
            }
        )

        # Закрытые задачи
        builder.add_task_list(
            "tasks_closed",
            filters={
                "RESPONSIBLE_ID": self.user_id,
                ">=CLOSED_DATE": from_str,
                "<=CLOSED_DATE": to_str,
            }
        )

        # Активные задачи
        builder.add_task_list(
            "tasks_active",
            filters={
                "RESPONSIBLE_ID": self.user_id,
                "!STATUS": "5",  # Не завершённые
            }
        )

        # Выполнить batch запрос
        batch_result = await self.client.batch(builder.build())

        # Парсинг результатов
        return {
            "created": self._parse_tasks(batch_result.get("tasks_created", {})),
            "assigned": self._parse_tasks(batch_result.get("tasks_assigned", {})),
            "closed": self._parse_tasks(batch_result.get("tasks_closed", {})),
            "active": self._parse_tasks(batch_result.get("tasks_active", {})),
        }

    def _parse_tasks(self, batch_result: Dict[str, Any]) -> List[Task]:
        """Распарсить задачи из batch результата."""
        if not batch_result or "tasks" not in batch_result:
            return []

        tasks = []
        for task_data in batch_result["tasks"]:
            try:
                task = Task(
                    id=str(task_data["id"]),
                    title=task_data.get("title", "Без названия"),
                    status=task_data.get("status", "0"),
                    responsible_id=str(task_data.get("responsibleId", "")),
                    creator_id=str(task_data.get("createdBy", "")),
                    created_date=parse_bitrix_datetime(task_data.get("createdDate", "")),
                    closed_date=parse_bitrix_datetime(task_data.get("closedDate")) if task_data.get("closedDate") else None,
                    deadline=parse_bitrix_datetime(task_data.get("deadline")) if task_data.get("deadline") else None,
                )
                tasks.append(task)
            except Exception as e:
                self._log(f"Ошибка парсинга задачи {task_data.get('id')}: {e}")

        return tasks

    async def collect_recently_active_task_ids(
        self,
        date_from: datetime,
    ) -> List[str]:
        """
        Собрать ID задач с недавней активностью, где пользователь участник.

        Использует MEMBER фильтр (ответственный, соисполнитель, наблюдатель)
        и сортировку по ACTIVITY_DATE desc, чтобы найти задачи с треком.
        """
        self._log(f"Сбор задач с активностью после {date_from}")

        from_str = format_bitrix_date_filter(date_from)

        result = await self.client.paginated_call(
            "tasks.task.list",
            params={
                "filter": {
                    "MEMBER": self.user_id,
                    ">=ACTIVITY_DATE": from_str,
                },
                "select": ["ID"],
                "order": {"ACTIVITY_DATE": "desc"},
            },
            max_pages=4,  # До 200 задач
        )

        task_ids = [str(t.get("id", t.get("ID", ""))) for t in result if t]
        self._log(f"Найдено {len(task_ids)} задач с недавней активностью")
        return task_ids

    async def collect_time_entries(
        self,
        task_ids: List[str],
        date_from: datetime,
        date_to: datetime,
    ) -> List[TimeEntry]:
        """
        Собрать трудозатраты по списку задач через batch запросы.

        Поддерживает >50 задач — разбивает на несколько batch-вызовов.
        """
        if not task_ids:
            return []

        self._log(f"Сбор трудозатрат по {len(task_ids)} задачам")

        entries = []
        # Разбить на чанки по 50 (лимит batch)
        for i in range(0, len(task_ids), 50):
            chunk = task_ids[i:i + 50]
            self._log(f"  batch {i // 50 + 1}: {len(chunk)} задач")

            builder = BatchRequestBuilder()
            for task_id in chunk:
                builder.add_time_entries(f"time_{task_id}", task_id)

            batch_result = await self.client.batch(builder.build())

            for key, result in batch_result.items():
                if not result or not isinstance(result, list):
                    continue

                for entry_data in result:
                    try:
                        created_date = parse_bitrix_datetime(entry_data.get("CREATED_DATE", ""))

                        # Фильтр по дате
                        if not (date_from <= created_date <= date_to):
                            continue

                        # Фильтр по пользователю
                        if str(entry_data.get("USER_ID")) != self.user_id:
                            continue

                        entry = TimeEntry(
                            task_id=str(entry_data.get("TASK_ID", "")),
                            user_id=str(entry_data.get("USER_ID", "")),
                            seconds=int(entry_data.get("SECONDS", 0)),
                            comment=entry_data.get("COMMENT_TEXT", ""),
                            created_date=created_date,
                        )
                        entries.append(entry)
                    except Exception as e:
                        self._log(f"Ошибка парсинга трудозатрат: {e}")

        self._log(f"Собрано {len(entries)} записей трудозатрат")
        return entries

    async def collect_task_titles(
        self,
        task_ids: List[str],
    ) -> Dict[str, str]:
        """
        Получить названия задач по ID через batch запрос.

        Returns:
            Словарь {task_id: title}
        """
        if not task_ids:
            return {}

        titles = {}
        for i in range(0, len(task_ids), 50):
            chunk = task_ids[i:i + 50]
            builder = BatchRequestBuilder()
            for task_id in chunk:
                builder.add_task_list(
                    f"title_{task_id}",
                    filters={"ID": task_id},
                    select=["ID", "TITLE"],
                )

            batch_result = await self.client.batch(builder.build())
            for key, result in batch_result.items():
                if not result or "tasks" not in result:
                    continue
                for t in result["tasks"]:
                    titles[str(t["id"])] = t.get("title", "Без названия")

        return titles
