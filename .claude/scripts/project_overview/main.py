#!/usr/bin/env python3
"""
Project Overview — сбор данных по проекту (Метрика + Битрикс24).

Вывод: JSON в stdout для потребления SKILL.md.
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Добавить директорию скрипта в sys.path для абсолютных импортов
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config
from models import ProjectInfo, ProjectOverviewData, MetricaData, BitrixData

from api.metrica_client import MetricaClient
from api.bitrix_client import BitrixClient

from analyzers.project_finder import ProjectFinder
from analyzers.traffic import TrafficAnalyzer
from analyzers.goals import GoalsAnalyzer
from analyzers.tasks import TasksAnalyzer

from formatters.json_output import format_json


async def cmd_find(args, config):
    """Режим поиска проекта по имени."""
    has_metrica = bool(config.yandex_metrica_token)
    metrica = MetricaClient(config.yandex_metrica_token, debug=args.debug) if has_metrica else None
    async with BitrixClient(config.bitrix_webhook_url, debug=args.debug) as bitrix:
        finder = ProjectFinder(metrica, bitrix, debug=args.debug, refresh_cache=args.refresh_cache)
        results = await finder.find(args.find)
        if not has_metrica:
            results["metrica_counters"] = []
            results["_warning"] = "YANDEX_METRICA_TOKEN не задан — поиск только в Битрикс24"
        print(json.dumps(results, ensure_ascii=False, indent=2))


async def cmd_collect(args, config):
    """Режим сбора данных по проекту."""
    counter_id = args.counter_id
    group_id = args.group_id
    days = args.days

    # Период
    if args.date_from and args.date_to:
        date_from = args.date_from
        date_to = args.date_to
    else:
        date_to_dt = datetime.now()
        date_from_dt = date_to_dt - timedelta(days=days)
        date_from = date_from_dt.strftime("%Y-%m-%d")
        date_to = date_to_dt.strftime("%Y-%m-%d")

    # Предыдущий период для тренда (такой же длины)
    period_days = (datetime.strptime(date_to, "%Y-%m-%d") - datetime.strptime(date_from, "%Y-%m-%d")).days
    prev_to_dt = datetime.strptime(date_from, "%Y-%m-%d") - timedelta(days=1)
    prev_from_dt = prev_to_dt - timedelta(days=period_days)
    prev_date_from = prev_from_dt.strftime("%Y-%m-%d")
    prev_date_to = prev_to_dt.strftime("%Y-%m-%d")

    project = ProjectInfo(
        name=args.project_name or "",
        counter_id=counter_id,
        group_id=group_id,
    )

    data = ProjectOverviewData(
        project=project,
        period_from=date_from,
        period_to=date_to,
    )

    errors = []

    # Собираем данные Метрики (параллельно трафик + цели)
    if counter_id and not config.yandex_metrica_token:
        errors.append("YANDEX_METRICA_TOKEN не задан — данные Метрики пропущены")
        counter_id = None

    if counter_id:
        try:
            metrica = MetricaClient(config.yandex_metrica_token, debug=args.debug)
            traffic_analyzer = TrafficAnalyzer(metrica, debug=args.debug)
            goals_analyzer = GoalsAnalyzer(metrica, debug=args.debug)

            (summary, trend, sources), goals = await asyncio.gather(
                traffic_analyzer.collect(counter_id, date_from, date_to, prev_date_from, prev_date_to),
                goals_analyzer.collect(counter_id, date_from, date_to),
            )

            data.metrica = MetricaData(
                summary=summary,
                trend=trend,
                sources=sources,
                goals=goals,
            )
        except Exception as e:
            errors.append(f"Metrica error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc(file=sys.stderr)

    # Собираем данные Битрикс24
    if group_id:
        try:
            async with BitrixClient(config.bitrix_webhook_url, debug=args.debug) as bitrix:
                tasks_analyzer = TasksAnalyzer(bitrix, debug=args.debug)
                data.bitrix = await tasks_analyzer.collect(group_id)
        except Exception as e:
            errors.append(f"Bitrix error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc(file=sys.stderr)

    data.errors = errors
    print(format_json(data))


async def main_async(args):
    """Основная асинхронная функция."""
    try:
        config = load_config()
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        sys.exit(1)

    if args.find:
        await cmd_find(args, config)
    else:
        await cmd_collect(args, config)


def main():
    """Точка входа."""
    parser = argparse.ArgumentParser(
        description="Project Overview — сбор данных по проекту (Метрика + Битрикс24)"
    )

    # Режим поиска
    parser.add_argument(
        "--find",
        help="Поиск проекта по имени в Метрике и Битрикс24",
    )

    # Режим сбора данных
    parser.add_argument(
        "--counter-id",
        help="ID счётчика Яндекс.Метрики",
    )
    parser.add_argument(
        "--group-id",
        help="ID рабочей группы Битрикс24",
    )
    parser.add_argument(
        "--project-name",
        help="Название проекта (для отображения в отчёте)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Период в днях (по умолчанию: 30)",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        help="Начало периода (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        help="Конец периода (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Обновить кэш списков групп/счётчиков",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Включить отладочный вывод",
    )

    args = parser.parse_args()

    # Валидация
    if not args.find and not args.counter_id and not args.group_id:
        parser.error("Укажите --find для поиска или --counter-id / --group-id для сбора данных")

    if args.date_from and not args.date_to:
        parser.error("--to обязателен если указан --from")
    if args.date_to and not args.date_from:
        parser.error("--from обязателен если указан --to")

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
