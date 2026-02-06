#!/usr/bin/env python3
"""
Weekly Review - скрипт для генерации еженедельного обзора активности.

Использует:
- Batch API Bitrix24 для оптимизации запросов
- asyncio для параллельных операций
- Claude API для суммаризации чатов
"""

import asyncio
import argparse
import sys
from datetime import datetime
from typing import Tuple, Optional

from config import load_config
from date_utils import get_week_boundaries
from models import WeeklyReportData

from api.bitrix_client import BitrixClient

from analyzers.tasks import TaskAnalyzer
from analyzers.meetings import MeetingAnalyzer
from analyzers.git import GitAnalyzer

from formatters.markdown import MarkdownFormatter


class WeeklyReviewCollector:
    """Оркестратор сбора данных для еженедельного обзора."""

    def __init__(
        self,
        bitrix_client: BitrixClient,
        user_id: str,
        user_name: str,
        projects_dirs: str,
        cache_dir,
        debug: bool = False,
    ):
        self.bitrix = bitrix_client
        self.user_id = user_id
        self.user_name = user_name
        self.projects_dirs = projects_dirs
        self.debug = debug

        # Инициализация анализаторов
        self.task_analyzer = TaskAnalyzer(bitrix_client, user_id, debug)
        self.meeting_analyzer = MeetingAnalyzer(bitrix_client, user_id, debug)
        # Чаты НЕ собираются скриптом - это делает skill через субагент chat-digest
        self.git_analyzer = GitAnalyzer(
            cache_file=cache_dir / "projects-cache.json",
            debug=debug,
        )

    def _log(self, message: str):
        """Вывести отладочное сообщение."""
        if self.debug:
            print(f"[WeeklyReview] {message}", file=sys.stderr)

    async def collect_all(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> WeeklyReportData:
        """
        Собрать все данные параллельно.

        Args:
            date_from: Начало периода
            date_to: Конец периода

        Returns:
            WeeklyReportData со всеми собранными данными
        """
        self._log(f"Начинаю сбор данных за период {date_from} — {date_to}")

        # Параллельный сбор данных (БЕЗ чатов - они собираются skill через субагент)
        (
            tasks_data,
            meetings,
            git_activity,
        ) = await asyncio.gather(
            self.task_analyzer.collect_tasks(date_from, date_to),
            self.meeting_analyzer.collect_meetings(date_from, date_to),
            self.git_analyzer.analyze_period(self.projects_dirs, date_from, date_to),
        )

        # Чаты не собираются - skill вызовет субагент chat-digest отдельно
        chat_summaries = []

        # Собрать уникальные ID задач для загрузки трудозатрат
        task_ids = set()
        for task_list in tasks_data.values():
            task_ids.update(task.id for task in task_list)

        # Загрузить трудозатраты
        time_entries = []
        if task_ids:
            time_entries = await self.task_analyzer.collect_time_entries(
                list(task_ids), date_from, date_to
            )

        self._log("Сбор данных завершён")

        return WeeklyReportData(
            user_id=self.user_id,
            user_name=self.user_name,
            date_from=date_from,
            date_to=date_to,
            tasks_created=tasks_data.get("created", []),
            tasks_assigned=tasks_data.get("assigned", []),
            tasks_closed=tasks_data.get("closed", []),
            tasks_active=tasks_data.get("active", []),
            meetings=meetings,
            chat_summaries=chat_summaries,
            time_entries=time_entries,
            git_activity=git_activity,
        )


async def get_user_profile(bitrix: BitrixClient) -> Tuple[str, str]:
    """
    Получить профиль текущего пользователя.

    Returns:
        Кортеж (user_id, user_name)
    """
    profile = await bitrix.call("user.current")

    if not profile:
        raise RuntimeError("Не удалось получить профиль пользователя")

    user_id = str(profile.get("ID", ""))
    first_name = profile.get("NAME", "")
    last_name = profile.get("LAST_NAME", "")
    user_name = f"{first_name} {last_name}".strip() or "Неизвестный"

    return user_id, user_name


async def main_async(args):
    """Основная асинхронная функция."""
    # Загрузить конфигурацию
    try:
        config = load_config()
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        print("\nУбедитесь, что .env файл содержит:", file=sys.stderr)
        print("  BITRIX24_WEBHOOK_URL=...", file=sys.stderr)
        print("  ANTHROPIC_API_KEY=...", file=sys.stderr)
        sys.exit(1)

    # Вычислить период
    if args.date_from and args.date_to:
        date_from = datetime.strptime(args.date_from, "%Y-%m-%d")
        date_to = datetime.strptime(args.date_to, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )
    else:
        week = args.week or "current"
        date_from, date_to = get_week_boundaries(week)

    # Инициализация клиентов
    async with BitrixClient(config.bitrix_webhook_url, args.debug) as bitrix:

        # Получить профиль пользователя
        try:
            user_id, user_name = await get_user_profile(bitrix)
        except RuntimeError as e:
            print(f"Ошибка: {e}", file=sys.stderr)
            sys.exit(1)

        # Инициализация коллектора
        # Суммаризация чатов будет делаться субагентом chat-digest из skill
        collector = WeeklyReviewCollector(
            bitrix_client=bitrix,
            user_id=user_id,
            user_name=user_name,
            projects_dirs=config.projects_dirs,
            cache_dir=config.cache_dir,
            debug=args.debug,
        )

        # Сбор данных
        data = await collector.collect_all(date_from, date_to)

        # Форматирование отчёта
        formatter = MarkdownFormatter()
        report = formatter.format_report(data)

        # Вывод
        print(report)


def main():
    """Точка входа."""
    parser = argparse.ArgumentParser(
        description="Weekly Review - еженедельный обзор активности"
    )
    parser.add_argument(
        "--week",
        choices=["current", "last"],
        help="Период: текущая или прошлая неделя (по умолчанию: current)",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        help="Начало периода (формат: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        help="Конец периода (формат: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Включить отладочный вывод",
    )

    args = parser.parse_args()

    # Валидация аргументов
    if args.date_from and not args.date_to:
        parser.error("--to обязателен если указан --from")
    if args.date_to and not args.date_from:
        parser.error("--from обязателен если указан --to")

    # Запуск
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nПрервано пользователем", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Критическая ошибка: {e}", file=sys.stderr)
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
