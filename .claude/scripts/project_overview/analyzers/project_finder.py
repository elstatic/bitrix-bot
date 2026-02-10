"""Поиск проекта по имени в Метрике и Битрикс24 (с файловым кэшем)."""

import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from api.metrica_client import MetricaClient
from api.bitrix_client import BitrixClient

CACHE_DIR = Path.home() / ".cache" / "project-overview"
CACHE_TTL = 24 * 3600  # 24 часа


def _read_cache(name: str) -> Optional[List[Dict[str, Any]]]:
    """Прочитать кэш, если он свежий."""
    path = CACHE_DIR / f"{name}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data.get("ts", 0) < CACHE_TTL:
            return data["items"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _write_cache(name: str, items: List[Dict[str, Any]]):
    """Записать кэш."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{name}.json"
    path.write_text(json.dumps({"ts": time.time(), "items": items}, ensure_ascii=False))


class ProjectFinder:
    """Поиск проекта по имени в Яндекс.Метрике и Битрикс24."""

    def __init__(
        self,
        metrica: Optional[MetricaClient],
        bitrix: BitrixClient,
        debug: bool = False,
        refresh_cache: bool = False,
    ):
        self.metrica = metrica
        self.bitrix = bitrix
        self.debug = debug
        self.refresh_cache = refresh_cache

    def _log(self, message: str):
        if self.debug:
            print(f"[ProjectFinder] {message}", file=sys.stderr)

    # ── Метрика ──────────────────────────────────────────────

    async def _load_metrica_counters(self) -> List[Dict[str, Any]]:
        """Загрузить все счётчики (из кэша или API)."""
        if not self.metrica:
            return []

        if not self.refresh_cache:
            cached = _read_cache("metrica_counters")
            if cached is not None:
                self._log(f"Метрика: кэш ({len(cached)} счётчиков)")
                return cached

        self._log("Метрика: загружаю список счётчиков из API")
        try:
            counters = await self.metrica.get_counters()
            _write_cache("metrica_counters", counters)
            self._log(f"Метрика: загружено {len(counters)} счётчиков, кэш обновлён")
            return counters
        except Exception as e:
            self._log(f"Ошибка загрузки счётчиков: {e}")
            return []

    async def search_metrica(self, query: str) -> List[Dict[str, Any]]:
        """Поиск счётчиков по имени (локальная фильтрация кэша)."""
        if not self.metrica:
            self._log("Метрика не настроена, пропускаю поиск")
            return []

        counters = await self._load_metrica_counters()
        q = query.lower()
        return [
            c for c in counters
            if q in c.get("name", "").lower() or q in c.get("site", "").lower()
        ]

    # ── Битрикс24 ────────────────────────────────────────────

    async def _load_bitrix_groups(self) -> List[Dict[str, Any]]:
        """Загрузить все группы (из кэша или API с пагинацией)."""
        if not self.refresh_cache:
            cached = _read_cache("bitrix_groups")
            if cached is not None:
                self._log(f"Битрикс: кэш ({len(cached)} групп)")
                return cached

        self._log("Битрикс: загружаю список групп из API")
        all_groups = []
        start = 0
        max_pages = 25

        try:
            for _ in range(max_pages):
                raw = await self.bitrix.call_raw(
                    "socialnetwork.api.workgroup.list",
                    {"select": ["ID", "NAME"], "start": start},
                )
                if not raw:
                    break

                result = raw.get("result", {})
                workgroups = result.get("workgroups", [])
                if not workgroups:
                    break

                for g in workgroups:
                    all_groups.append({
                        "id": str(g.get("id", g.get("ID", ""))),
                        "name": g.get("name", g.get("NAME", "")),
                    })

                next_start = raw.get("next")
                if not next_start:
                    break
                start = next_start

            _write_cache("bitrix_groups", all_groups)
            self._log(f"Битрикс: загружено {len(all_groups)} групп, кэш обновлён")
            return all_groups
        except Exception as e:
            self._log(f"Ошибка загрузки групп: {e}")
            return []

    async def search_bitrix_groups(self, query: str) -> List[Dict[str, Any]]:
        """Поиск групп по имени (локальная фильтрация кэша)."""
        groups = await self._load_bitrix_groups()
        q = query.lower()
        return [g for g in groups if q in g.get("name", "").lower()]

    # ── Общий поиск ──────────────────────────────────────────

    async def find(self, query: str) -> Dict[str, Any]:
        """Поиск проекта одновременно в Метрике и Битрикс24."""
        import asyncio
        counters, groups = await asyncio.gather(
            self.search_metrica(query),
            self.search_bitrix_groups(query),
        )
        self._log(f"Найдено: {len(counters)} счётчиков, {len(groups)} групп")
        return {
            "metrica_counters": counters,
            "bitrix_groups": groups,
        }
