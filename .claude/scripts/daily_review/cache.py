"""Кеширование результатов для Daily Review."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


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

    def get(self, key: str) -> Optional[Any]:
        path = self._path_for_key(key)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text())
            ts = datetime.fromisoformat(data.get("timestamp"))
            age = (datetime.now() - ts).total_seconds()
            if age > self.ttl_seconds:
                return None
            if data.get("key") != key:
                return None
            return data.get("payload")
        except Exception:
            return None

    def set(self, key: str, payload: Any):
        entry = CacheEntry(key=key, timestamp=datetime.now().isoformat(), payload=payload)
        path = self._path_for_key(key)
        path.write_text(json.dumps(entry.__dict__, ensure_ascii=False, indent=2))
