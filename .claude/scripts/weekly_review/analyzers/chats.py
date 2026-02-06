"""Анализатор чатов из Bitrix24 с суммаризацией через Claude."""

import asyncio
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

from ..api.bitrix_client import BitrixClient
from ..api.claude_client import ClaudeClient
from ..models import DialogSummary
from ..date_utils import parse_bitrix_datetime


class ChatAnalyzer:
    """Анализ чатов и переписок."""

    def __init__(
        self,
        bitrix_client: BitrixClient,
        claude_client: Optional[ClaudeClient],
        user_id: str,
        user_name: str,
        debug: bool = False,
    ):
        self.bitrix = bitrix_client
        self.claude = claude_client
        self.user_id = user_id
        self.user_name = user_name
        self.debug = debug

    def _log(self, message: str):
        """Вывести отладочное сообщение."""
        if self.debug:
            print(f"[ChatAnalyzer] {message}", file=sys.stderr)

    async def collect_and_summarize(
        self,
        date_from: datetime,
        date_to: datetime,
        chat_limit: int = 200,
        top_dialogs: int = 15,
    ) -> List[DialogSummary]:
        """
        Собрать чаты и суммаризовать их через Claude.

        Args:
            date_from: Начало периода
            date_to: Конец периода
            chat_limit: Сколько чатов загрузить из im.recent.list
            top_dialogs: Сколько топ диалогов включить в финальный отчёт

        Returns:
            Список суммаризованных диалогов
        """
        self._log(f"Сбор чатов за период {date_from} — {date_to}")

        # Шаг 1: Получить список недавних чатов
        recent_chats = await self._get_recent_chats(chat_limit)
        if not recent_chats:
            self._log("Недавние чаты не найдены")
            return []

        self._log(f"Найдено {len(recent_chats)} недавних чатов")

        # Шаг 2: Параллельно загрузить сообщения из каждого чата
        chat_messages = await asyncio.gather(*[
            self._fetch_dialog_messages(chat, date_from, date_to)
            for chat in recent_chats
        ])

        # Фильтровать пустые диалоги
        active_dialogs = [
            (chat, messages)
            for chat, messages in zip(recent_chats, chat_messages)
            if messages
        ]

        self._log(f"Активных диалогов с сообщениями: {len(active_dialogs)}")

        if not active_dialogs:
            return []

        # Шаг 3: Параллельно суммаризовать через Claude (если доступен)
        if self.claude:
            summaries = await asyncio.gather(*[
                self.claude.summarize_dialog(
                    dialog_id=chat["id"],
                    dialog_name=chat["name"],
                    messages=messages,
                    user_name=self.user_name,
                )
                for chat, messages in active_dialogs
            ])
        else:
            # Без суммаризации - создаём упрощённые записи
            self._log("Claude API недоступен, пропускаем суммаризацию")
            summaries = [
                DialogSummary(
                    dialog_id=chat["id"],
                    dialog_name=chat["name"],
                    message_count=len(messages),
                    topic="Чат без суммаризации (требуется ANTHROPIC_API_KEY)",
                    agreements=[],
                    decisions=[],
                    questions=[],
                    awaits_response=False,
                )
                for chat, messages in active_dialogs
            ]

        # Фильтровать None (ошибки суммаризации)
        valid_summaries = [s for s in summaries if s is not None]

        # Сортировать по количеству сообщений и взять топ
        valid_summaries.sort(key=lambda s: s.message_count, reverse=True)
        top_summaries = valid_summaries[:top_dialogs]

        self._log(f"Успешно суммаризовано {len(valid_summaries)} диалогов, топ {len(top_summaries)}")
        return top_summaries

    async def _get_recent_chats(self, limit: int) -> List[Dict[str, Any]]:
        """Получить список недавних чатов."""
        params = {
            "SKIP_OPENLINES": "Y",
            "LIMIT": limit,
        }

        result = await self.bitrix.call("im.recent.list", params)

        if not result or not isinstance(result, dict):
            return []

        items = result.get("items", [])

        # Фильтровать служебные чаты
        filtered = []
        for item in items:
            chat_type = item.get("type", "")
            chat_id = item.get("id", "")

            # Пропустить служебные чаты
            if chat_type in ["announcement", "support24"]:
                continue

            filtered.append({
                "id": chat_id,
                "name": item.get("title", "Без названия"),
                "type": chat_type,
            })

        return filtered

    async def _fetch_dialog_messages(
        self,
        chat: Dict[str, Any],
        date_from: datetime,
        date_to: datetime,
        max_pages: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Загрузить сообщения диалога с пагинацией.

        Args:
            chat: Информация о чате
            date_from: Начало периода
            date_to: Конец периода
            max_pages: Максимум страниц для пагинации

        Returns:
            Список сообщений
        """
        dialog_id = chat["id"]
        all_messages = []
        last_id = None

        for page in range(max_pages):
            params = {
                "DIALOG_ID": dialog_id,
                "LIMIT": 20,
            }

            if last_id:
                params["LAST_ID"] = last_id

            result = await self.bitrix.call("im.dialog.messages.get", params)

            if not result or not isinstance(result, dict):
                break

            messages = result.get("messages", [])
            if not messages:
                break

            # Фильтровать по дате
            for msg in messages:
                try:
                    msg_date = parse_bitrix_datetime(msg.get("date", ""))
                    if date_from <= msg_date <= date_to:
                        all_messages.append({
                            "text": msg.get("text", ""),
                            "author_name": msg.get("author_name", "Неизвестный"),
                            "date": msg.get("date", ""),
                        })
                except Exception:
                    continue

            # Обновить last_id для следующей страницы
            last_id = messages[-1].get("id")

        # Исключить монологи (все сообщения от одного автора)
        if all_messages:
            unique_authors = set(msg["author_name"] for msg in all_messages)
            if len(unique_authors) < 2:
                return []

        return all_messages
