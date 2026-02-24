"""Анализатор git активности в локальных проектах."""

import asyncio
import sys
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from models import GitActivity


class GitAnalyzer:
    """Анализ git активности."""

    def __init__(self, cache_file: Path, debug: bool = False):
        self.cache_file = cache_file
        self.debug = debug
        self._projects_cache: Optional[List[str]] = None

    @staticmethod
    def _parse_projects_dirs(projects_dirs: str) -> List[Path]:
        """Разобрать PROJECTS_DIRS с поддержкой Unix/Windows форматов."""
        raw = (projects_dirs or "").strip()
        if not raw:
            return []

        parts: List[str]
        if os.pathsep in raw:
            parts = raw.split(os.pathsep)
        elif ";" in raw:
            parts = raw.split(";")
        elif ":" in raw and not re.match(r"^[A-Za-z]:[\\/]", raw):
            # Legacy-разделитель ":" (актуален для Unix-окружений).
            parts = raw.split(":")
        else:
            parts = [raw]

        roots: List[Path] = []
        for part in parts:
            item = part.strip()
            if not item:
                continue
            path = Path(item).expanduser()
            if path.exists():
                roots.append(path)

        return roots

    def _log(self, message: str):
        """Вывести отладочное сообщение."""
        if self.debug:
            print(f"[GitAnalyzer] {message}", file=sys.stderr)

    async def analyze_period(
        self,
        projects_dirs: str,
        date_from: datetime,
        date_to: datetime,
    ) -> List[GitActivity]:
        """
        Анализировать git активность за период.

        Args:
            projects_dirs: Путь к папке с проектами
            date_from: Начало периода
            date_to: Конец периода

        Returns:
            Список GitActivity для активных проектов
        """
        if not projects_dirs or not projects_dirs.strip():
            self._log("PROJECTS_DIRS не задан — пропускаю анализ git активности")
            return []

        self._log(f"Анализ git активности в {projects_dirs}")

        # Получить список проектов (с кешем)
        projects = await self._get_projects(projects_dirs)

        if not projects:
            self._log("Проекты не найдены")
            return []

        # Параллельно проанализировать каждый проект
        activities = await asyncio.gather(*[
            self._analyze_project(project, date_from, date_to)
            for project in projects
        ])

        # Фильтровать пустые результаты
        active_projects = [a for a in activities if a and a.commits]

        self._log(f"Активных проектов: {len(active_projects)}")
        return active_projects

    async def _get_projects(self, projects_dirs: str) -> List[str]:
        """
        Получить список git репозиториев с кешированием.

        Кеш действителен 24 часа.
        """
        roots = self._parse_projects_dirs(projects_dirs)
        if not roots:
            self._log("Не удалось разобрать PROJECTS_DIRS или директории не существуют")
            return []

        roots_key = [str(p) for p in roots]

        # Проверить кеш
        if self.cache_file.exists():
            try:
                cache_data = json.loads(self.cache_file.read_text())
                cache_time = datetime.fromisoformat(cache_data["timestamp"])
                cache_age = (datetime.now() - cache_time).total_seconds()
                cached_roots = cache_data.get("projects_dirs", [])

                # Кеш действителен 24 часа и только для того же набора корней.
                if cache_age < 86400 and cached_roots == roots_key:
                    self._log(f"Использую кеш проектов (возраст: {cache_age:.0f}s)")
                    return cache_data["projects"]
            except Exception as e:
                self._log(f"Ошибка чтения кеша: {e}")

        # Сканировать директорию
        self._log(f"Сканирую корни для поиска git репозиториев: {roots_key}")

        projects = []
        for root in roots:
            for item in root.iterdir():
                if item.is_dir() and (item / ".git").exists():
                    projects.append(str(item))

        # Сохранить в кеш
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "projects_dirs": roots_key,
                "projects": projects,
            }
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(cache_data, indent=2))
            self._log(f"Кеш обновлён: {len(projects)} проектов")
        except Exception as e:
            self._log(f"Ошибка записи кеша: {e}")

        return projects

    async def _analyze_project(
        self,
        project_path: str,
        date_from: datetime,
        date_to: datetime,
    ) -> Optional[GitActivity]:
        """
        Проанализировать один проект.

        Args:
            project_path: Путь к проекту
            date_from: Начало периода
            date_to: Конец периода
        """
        path = Path(project_path)
        project_name = path.name

        try:
            # Получить коммиты за период
            since = date_from.strftime("%Y-%m-%d 00:00:00")
            until = date_to.strftime("%Y-%m-%d 23:59:59")

            # git log с форматированием
            log_cmd = [
                "git", "-C", str(path), "log",
                f"--since={since}",
                f"--until={until}",
                "--pretty=format:%H|%s|%ai",
                "--no-merges",
            ]

            process = await asyncio.create_subprocess_exec(
                *log_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return None

            # Парсинг коммитов
            commits = []
            for line in stdout.decode("utf-8").strip().split("\n"):
                if not line:
                    continue

                parts = line.split("|", 2)
                if len(parts) == 3:
                    commits.append({
                        "hash": parts[0][:7],
                        "message": parts[1],
                        "date": parts[2],
                    })

            if not commits:
                return None

            # Статистика изменений за период.
            stat_cmd = [
                "git", "-C", str(path), "log",
                f"--since={since}",
                f"--until={until}",
                "--pretty=tformat:",
                "--shortstat",
                "--no-merges",
            ]

            process = await asyncio.create_subprocess_exec(
                *stat_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            # Парсинг статистики
            files_changed = 0
            insertions = 0
            deletions = 0

            stat_text = stdout.decode("utf-8").strip()
            if stat_text:
                for line in stat_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = [p.strip() for p in line.split(",")]
                    for part in parts:
                        tokens = part.split()
                        if not tokens:
                            continue
                        if "file" in part:
                            files_changed += int(tokens[0])
                        elif "insertion" in part:
                            insertions += int(tokens[0])
                        elif "deletion" in part:
                            deletions += int(tokens[0])

            return GitActivity(
                project_name=project_name,
                project_path=str(path),
                commits=commits,
                files_changed=files_changed,
                insertions=insertions,
                deletions=deletions,
            )

        except Exception as e:
            self._log(f"Ошибка анализа проекта {project_name}: {e}")
            return None
