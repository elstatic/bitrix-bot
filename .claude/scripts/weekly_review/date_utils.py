"""Утилиты для работы с датами."""

from datetime import datetime, timedelta
from typing import Tuple


def get_week_boundaries(week: str = "current") -> Tuple[datetime, datetime]:
    """
    Получить границы недели.

    Args:
        week: "current" или "last"

    Returns:
        Кортеж (date_from, date_to) - начало и конец недели
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Найти понедельник текущей недели (weekday: 0 = Monday)
    days_since_monday = today.weekday()
    current_week_monday = today - timedelta(days=days_since_monday)

    if week == "current":
        date_from = current_week_monday
        date_to = current_week_monday + timedelta(days=6, hours=23, minutes=59, seconds=59)
    elif week == "last":
        date_from = current_week_monday - timedelta(days=7)
        date_to = current_week_monday - timedelta(seconds=1)
    else:
        raise ValueError(f"Неизвестный период: {week}. Используйте 'current' или 'last'")

    return date_from, date_to


def parse_bitrix_datetime(dt_str: str) -> datetime:
    """
    Парсинг даты из формата Bitrix24.

    Примеры форматов:
    - "2026-02-06T10:30:00+03:00"
    - "2026-02-06 10:30:00"
    """
    if not dt_str:
        return None

    # Удалить таймзону если есть
    if '+' in dt_str:
        dt_str = dt_str.split('+')[0]
    elif 'Z' in dt_str:
        dt_str = dt_str.replace('Z', '')

    # Попробовать разные форматы
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue

    raise ValueError(f"Не удалось распарсить дату: {dt_str}")


def format_date_range(date_from: datetime, date_to: datetime) -> str:
    """Отформатировать диапазон дат для вывода."""
    return f"{date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}"


def format_bitrix_date_filter(dt: datetime) -> str:
    """Формат даты для фильтров Bitrix24 API."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")
