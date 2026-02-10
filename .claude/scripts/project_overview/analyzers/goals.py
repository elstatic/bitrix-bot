"""Сбор данных о целях и конверсиях."""

import sys
from typing import List

from api.metrica_client import MetricaClient
from models import GoalStats


class GoalsAnalyzer:
    """Сбор целей и статистики конверсий."""

    def __init__(self, metrica: MetricaClient, debug: bool = False):
        self.metrica = metrica
        self.debug = debug

    def _log(self, message: str):
        if self.debug:
            print(f"[GoalsAnalyzer] {message}", file=sys.stderr)

    async def collect(
        self,
        counter_id: str,
        date_from: str,
        date_to: str,
    ) -> List[GoalStats]:
        """Получить цели и их статистику за период."""
        # Получить список целей
        goals_list = await self.metrica.get_goals(counter_id)
        if not goals_list:
            self._log("Целей не найдено")
            return []

        goal_ids = [g["id"] for g in goals_list]
        goal_names = {g["id"]: g["name"] for g in goals_list}

        self._log(f"Найдено {len(goal_ids)} целей, загружаю статистику")

        # Получить статистику
        stats = await self.metrica.get_goals_stats(counter_id, date_from, date_to, goal_ids)

        results = []
        for gid in goal_ids:
            s = stats.get(gid, {})
            results.append(GoalStats(
                id=gid,
                name=goal_names.get(gid, ""),
                reaches=s.get("reaches", 0),
                cr=s.get("cr", 0.0),
            ))

        # Сортировать по количеству достижений (убывание)
        results.sort(key=lambda g: g.reaches, reverse=True)
        self._log(f"Статистика по {len(results)} целям загружена")
        return results
