"""Builder для формирования batch запросов к Bitrix24."""

from typing import Dict, Any
from urllib.parse import quote


def _encode_filter_key(key: str) -> str:
    """URL-кодировать операторы сравнения в ключе фильтра Bitrix24.

    Bitrix24 batch API требует кодирования >=, <=, >, <, ! в ключах фильтров,
    иначе фильтр игнорируется.
    """
    return quote(key, safe="ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz")


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
        if select is None:
            select = ["ID", "TITLE", "STATUS", "RESPONSIBLE_ID", "CREATOR_ID",
                     "CREATED_DATE", "CLOSED_DATE", "DEADLINE"]

        filter_parts = [f"filter[{_encode_filter_key(k)}]={v}" for k, v in filters.items()]
        select_parts = [f"select[]={field}" for field in select]
        query = "&".join(filter_parts + select_parts)

        self.commands[key] = f"tasks.task.list?{query}"
        return self

    def add_sonet_group_list(
        self,
        key: str,
        filters: Dict[str, Any] = None,
    ) -> "BatchRequestBuilder":
        """Добавить запрос на получение списка рабочих групп."""
        filters = filters or {}
        filter_parts = [f"filter[{_encode_filter_key(k)}]={v}" for k, v in filters.items()]
        query = "&".join(filter_parts) if filter_parts else ""
        self.commands[key] = f"sonet_group.get?{query}" if not query else f"sonet_group.get?{query}"
        return self

    def build(self) -> Dict[str, str]:
        return self.commands

    def clear(self) -> "BatchRequestBuilder":
        self.commands = {}
        return self
