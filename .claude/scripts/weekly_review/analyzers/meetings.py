"""Анализатор встреч из календаря Bitrix24."""

import sys
from datetime import datetime
from typing import List, Dict, Any

from ..api.bitrix_client import BitrixClient
from ..models import Meeting
from ..date_utils import parse_bitrix_datetime


class MeetingAnalyzer:
    """Анализ встреч из календаря."""

    def __init__(self, client: BitrixClient, user_id: str, debug: bool = False):
        self.client = client
        self.user_id = user_id
        self.debug = debug

    def _log(self, message: str):
        """Вывести отладочное сообщение."""
        if self.debug:
            print(f"[MeetingAnalyzer] {message}", file=sys.stderr)

    async def collect_meetings(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> List[Meeting]:
        """
        Собрать встречи за период.

        Args:
            date_from: Начало периода
            date_to: Конец периода
        """
        self._log(f"Сбор встреч за период {date_from} — {date_to}")

        params = {
            "type": "user",
            "ownerId": self.user_id,
            "from": date_from.strftime("%Y-%m-%d"),
            "to": date_to.strftime("%Y-%m-%d"),
        }

        result = await self.client.call("calendar.event.get", params)

        if not result or not isinstance(result, list):
            self._log("Встречи не найдены или ошибка API")
            return []

        meetings = []
        for event_data in result:
            try:
                meeting = Meeting(
                    id=str(event_data.get("ID", "")),
                    name=event_data.get("NAME", "Без названия"),
                    date_from=parse_bitrix_datetime(event_data.get("DATE_FROM", "")),
                    date_to=parse_bitrix_datetime(event_data.get("DATE_TO", "")),
                    attendees=self._parse_attendees(event_data.get("ATTENDEES", [])),
                    location=event_data.get("LOCATION", ""),
                )
                meetings.append(meeting)
            except Exception as e:
                self._log(f"Ошибка парсинга встречи {event_data.get('ID')}: {e}")

        self._log(f"Собрано {len(meetings)} встреч")
        return meetings

    def _parse_attendees(self, attendees_data: List[Any]) -> List[str]:
        """Извлечь список участников."""
        if not attendees_data:
            return []

        attendees = []
        for attendee in attendees_data:
            if isinstance(attendee, dict):
                name = attendee.get("NAME", attendee.get("DISPLAY_NAME", ""))
                if name:
                    attendees.append(name)

        return attendees
