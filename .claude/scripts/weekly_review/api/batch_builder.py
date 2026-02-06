"""Builder для формирования batch запросов к Bitrix24."""

from datetime import datetime
from typing import Dict, Any
from urllib.parse import urlencode


class BatchRequestBuilder:
    """Helper для построения batch команд."""

    def __init__(self):
        self.commands: Dict[str, str] = {}

    def add_task_list(
        self,
        key: str,
        filters: Dict[str, Any],
        select: list[str] = None,
    ) -> "BatchRequestBuilder":
        """
        Добавить запрос на получение списка задач.

        Args:
            key: Ключ для результата в batch ответе
            filters: Фильтры для tasks.task.list
            select: Поля для выборки
        """
        if select is None:
            select = ["ID", "TITLE", "STATUS", "RESPONSIBLE_ID", "CREATOR_ID",
                     "CREATED_DATE", "CLOSED_DATE", "DEADLINE"]

        params = {
            "filter": filters,
            "select": select,
        }

        # Сформировать строку запроса
        filter_parts = [f"filter[{k}]={v}" for k, v in filters.items()]
        select_parts = [f"select[]={field}" for field in select]
        query = "&".join(filter_parts + select_parts)

        self.commands[key] = f"tasks.task.list?{query}"
        return self

    def add_time_entries(
        self,
        key: str,
        task_id: str,
    ) -> "BatchRequestBuilder":
        """
        Добавить запрос на получение трудозатрат по задаче.

        Args:
            key: Ключ для результата
            task_id: ID задачи
        """
        self.commands[key] = f"task.elapseditem.getlist?TASKID={task_id}"
        return self

    def add_calendar_events(
        self,
        key: str,
        user_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> "BatchRequestBuilder":
        """
        Добавить запрос на получение событий календаря.

        Args:
            key: Ключ для результата
            user_id: ID пользователя
            date_from: Начало периода
            date_to: Конец периода
        """
        from_str = date_from.strftime("%Y-%m-%d")
        to_str = date_to.strftime("%Y-%m-%d")

        params = {
            "type": "user",
            "ownerId": user_id,
            "from": from_str,
            "to": to_str,
        }

        query = urlencode(params)
        self.commands[key] = f"calendar.event.get?{query}"
        return self

    def build(self) -> Dict[str, str]:
        """Получить сформированные команды для batch запроса."""
        return self.commands

    def clear(self) -> "BatchRequestBuilder":
        """Очистить команды."""
        self.commands = {}
        return self
