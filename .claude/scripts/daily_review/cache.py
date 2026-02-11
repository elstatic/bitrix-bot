"""Кеширование результатов для Daily Review."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple


@dataclass
class CacheEntry:
    key: str
    timestamp: str
    payload: Any


class JsonCache:
    """Простой JSON кеш по ключу в отдельном файле."""

    def __init__(self, base_dir: Path, ttl_seconds: int = 86400):
        self.base_dir = base_dir
        self.ttl_seconds = ttl_seconds
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_key(self, key: str) -> Path:
        return self.base_dir / f"{key}.json"

    def _read_entry(self, key: str) -> Optional[Tuple[float, Any]]:
        """Прочитать запись и вернуть (age_seconds, payload) или None."""
        path = self._path_for_key(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if data.get("key") != key:
                return None
            ts = datetime.fromisoformat(data.get("timestamp"))
            age = (datetime.now() - ts).total_seconds()
            return age, data.get("payload")
        except Exception:
            return None

    def get(self, key: str) -> Optional[Any]:
        result = self._read_entry(key)
        if result is None:
            return None
        age, payload = result
        if age > self.ttl_seconds:
            return None
        return payload

    def get_if_fresh(self, key: str, max_age_seconds: int) -> Optional[Any]:
        """Получить данные с произвольным TTL (не зависит от self.ttl_seconds)."""
        result = self._read_entry(key)
        if result is None:
            return None
        age, payload = result
        if age > max_age_seconds:
            return None
        return payload

    def set(self, key: str, payload: Any):
        entry = CacheEntry(key=key, timestamp=datetime.now().isoformat(), payload=payload)
        path = self._path_for_key(key)
        path.write_text(json.dumps(entry.__dict__, ensure_ascii=False, indent=2))
