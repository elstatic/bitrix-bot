"""Async Yandex Metrica API клиент (stdlib only)."""

import asyncio
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

_executor = ThreadPoolExecutor(max_workers=4)

BASE_URL = "https://api-metrika.yandex.net"


class MetricaClient:
    """Асинхронный клиент для Yandex Metrica API (без внешних зависимостей)."""

    MAX_REQUESTS_PER_SECOND = 30

    def __init__(self, token: str, debug: bool = False):
        self.token = token
        self.debug = debug
        self._last_request_time: float = 0.0

    def _log(self, message: str):
        if self.debug:
            print(f"[MetricaClient] {message}", file=sys.stderr)

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_request_time
        min_interval = 1.0 / self.MAX_REQUESTS_PER_SECOND
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    def _sync_get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Синхронный GET-запрос — вызывается в executor."""
        self._rate_limit()

        url = f"{BASE_URL}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"

        req = Request(url, headers={
            "Authorization": f"OAuth {self.token}",
            "Content-Type": "application/json",
        })

        self._log(f"GET {endpoint}")

        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        if "errors" in data:
            error_msg = "; ".join(err.get("text", "Unknown") for err in data["errors"])
            raise RuntimeError(f"Metrica API error: {error_msg}")

        return data

    async def _async_get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Async обёртка над синхронным GET через ThreadPoolExecutor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._sync_get, endpoint, params)

    async def get_counters(self, query: str = "") -> List[Dict[str, Any]]:
        """Получить список счётчиков. Если query — фильтр по search_string."""
        params = {"per_page": 10000}
        if query:
            params["search_string"] = query
        data = await self._async_get("/management/v1/counters", params)
        counters = data.get("counters", [])
        rows = data.get("rows", len(counters))
        self._log(f"Загружено {len(counters)}/{rows} счётчиков" + (f" по запросу '{query}'" if query else ""))
        return [
            {
                "id": str(c.get("id", "")),
                "name": c.get("name", ""),
                "site": c.get("site2", {}).get("site", c.get("site", "")),
                "status": c.get("status", ""),
            }
            for c in counters
        ]

    async def get_traffic_summary(
        self, counter_id: str, date_from: str, date_to: str,
    ) -> Dict[str, Any]:
        """Получить сводку по трафику за период."""
        data = await self._async_get("/stat/v1/data", {
            "ids": counter_id,
            "metrics": "ym:s:visits,ym:s:users,ym:s:bounceRate,ym:s:pageDepth,ym:s:avgVisitDurationSeconds",
            "date1": date_from,
            "date2": date_to,
            "accuracy": "full",
        })

        totals = data.get("totals", [])
        if len(totals) >= 5:
            return {
                "visits": int(totals[0]),
                "users": int(totals[1]),
                "bounce_rate": round(totals[2], 2),
                "page_depth": round(totals[3], 2),
                "avg_visit_duration": round(totals[4], 1),
            }
        return {}

    async def get_traffic_sources(
        self, counter_id: str, date_from: str, date_to: str,
    ) -> List[Dict[str, Any]]:
        """Получить трафик по источникам."""
        data = await self._async_get("/stat/v1/data", {
            "ids": counter_id,
            "metrics": "ym:s:visits,ym:s:users,ym:s:bounceRate",
            "dimensions": "ym:s:lastTrafficSource",
            "date1": date_from,
            "date2": date_to,
            "accuracy": "full",
            "sort": "-ym:s:visits",
        })

        sources = []
        for item in data.get("data", []):
            dims = item.get("dimensions", [])
            metrics = item.get("metrics", [])
            if dims and len(metrics) >= 3:
                sources.append({
                    "source": dims[0].get("name", "unknown"),
                    "visits": int(metrics[0]),
                    "users": int(metrics[1]),
                    "bounce_rate": round(metrics[2], 2),
                })
        return sources

    async def get_goals(self, counter_id: str) -> List[Dict[str, Any]]:
        """Получить список целей счётчика."""
        data = await self._async_get(f"/management/v1/counter/{counter_id}/goals")
        goals = data.get("goals", [])
        return [
            {
                "id": str(g.get("id", "")),
                "name": g.get("name", ""),
                "type": g.get("type", ""),
            }
            for g in goals
        ]

    async def get_goals_stats(
        self,
        counter_id: str,
        date_from: str,
        date_to: str,
        goal_ids: List[str],
    ) -> Dict[str, Dict[str, Any]]:
        """Получить статистику по целям (reaches + conversion rate).

        Returns:
            Dict[goal_id, {"reaches": int, "cr": float}]
        """
        if not goal_ids:
            return {}

        # API лимит ~20 метрик, базовые 1 (visits), на цель 2 (reaches + conversionRate)
        # = макс ~9 целей за запрос
        max_goals = 9
        batch_goals = goal_ids[:max_goals]

        metrics = ["ym:s:visits"]
        for gid in batch_goals:
            metrics.extend([
                f"ym:s:goal{gid}reaches",
                f"ym:s:goal{gid}conversionRate",
            ])

        data = await self._async_get("/stat/v1/data", {
            "ids": counter_id,
            "metrics": ",".join(metrics),
            "date1": date_from,
            "date2": date_to,
            "accuracy": "full",
        })

        totals = data.get("totals", [])
        result = {}

        # totals[0] = visits, далее пары (reaches, conversionRate) для каждой цели
        for i, gid in enumerate(batch_goals):
            base = 1 + i * 2
            if base + 1 < len(totals):
                result[gid] = {
                    "reaches": int(totals[base]),
                    "cr": round(totals[base + 1], 2),
                }

        return result
