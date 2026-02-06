"""Анализатор трудозатрат из Bitrix24."""

import sys
from datetime import datetime
from typing import List, Dict

from ..models import TimeEntry


class TimeTrackingAnalyzer:
    """Анализ трудозатрат."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def _log(self, message: str):
        """Вывести отладочное сообщение."""
        if self.debug:
            print(f"[TimeTrackingAnalyzer] {message}", file=sys.stderr)

    def analyze_time_entries(self, entries: List[TimeEntry]) -> Dict[str, float]:
        """
        Проанализировать трудозатраты и сгруппировать по задачам.

        Args:
            entries: Список записей трудозатрат

        Returns:
            Словарь {task_id: total_hours}
        """
        if not entries:
            return {}

        task_times = {}
        for entry in entries:
            task_id = entry.task_id
            task_times[task_id] = task_times.get(task_id, 0.0) + entry.hours

        self._log(f"Проанализировано трудозатрат по {len(task_times)} задачам")
        return task_times

    def get_total_time(self, entries: List[TimeEntry]) -> float:
        """Получить суммарное время в часах."""
        return sum(entry.hours for entry in entries)
