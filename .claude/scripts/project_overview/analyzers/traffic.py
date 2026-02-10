"""Сбор данных о трафике + тренд."""

import sys
from typing import Dict, Any, Tuple

from api.metrica_client import MetricaClient
from models import TrafficSummary, TrafficTrend, TrafficSource


def _calc_delta_pct(current: float, previous: float) -> float:
    """Вычислить дельту в процентах."""
    if previous == 0:
        return 0.0 if current == 0 else 100.0
    return round((current - previous) / previous * 100, 1)


class TrafficAnalyzer:
    """Сбор и анализ данных о трафике."""

    def __init__(self, metrica: MetricaClient, debug: bool = False):
        self.metrica = metrica
        self.debug = debug

    def _log(self, message: str):
        if self.debug:
            print(f"[TrafficAnalyzer] {message}", file=sys.stderr)

    async def collect(
        self,
        counter_id: str,
        date_from: str,
        date_to: str,
        prev_date_from: str,
        prev_date_to: str,
    ) -> Tuple[TrafficSummary, TrafficTrend, list]:
        """Собрать трафик за текущий и предыдущий периоды + источники.

        Returns:
            (summary, trend, sources)
        """
        import asyncio

        current, previous, sources_raw = await asyncio.gather(
            self.metrica.get_traffic_summary(counter_id, date_from, date_to),
            self.metrica.get_traffic_summary(counter_id, prev_date_from, prev_date_to),
            self.metrica.get_traffic_sources(counter_id, date_from, date_to),
        )

        summary = TrafficSummary(
            visits=current.get("visits", 0),
            users=current.get("users", 0),
            bounce_rate=current.get("bounce_rate", 0.0),
            page_depth=current.get("page_depth", 0.0),
            avg_visit_duration=current.get("avg_visit_duration", 0.0),
        )

        trend = TrafficTrend(
            visits_delta_pct=_calc_delta_pct(
                current.get("visits", 0), previous.get("visits", 0)),
            users_delta_pct=_calc_delta_pct(
                current.get("users", 0), previous.get("users", 0)),
            bounce_rate_delta_pct=_calc_delta_pct(
                current.get("bounce_rate", 0), previous.get("bounce_rate", 0)),
            page_depth_delta_pct=_calc_delta_pct(
                current.get("page_depth", 0), previous.get("page_depth", 0)),
            avg_visit_duration_delta_pct=_calc_delta_pct(
                current.get("avg_visit_duration", 0), previous.get("avg_visit_duration", 0)),
        )

        sources = [
            TrafficSource(
                source=s["source"],
                visits=s["visits"],
                users=s["users"],
                bounce_rate=s["bounce_rate"],
            )
            for s in sources_raw
        ]

        self._log(f"Трафик: {summary.visits} визитов, {len(sources)} источников")
        return summary, trend, sources
