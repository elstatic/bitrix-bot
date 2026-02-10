"""Модели данных для project overview."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ProjectInfo:
    """Информация о проекте."""
    name: str
    counter_id: str
    group_id: str


@dataclass
class TrafficSummary:
    """Сводка по трафику."""
    visits: int = 0
    users: int = 0
    bounce_rate: float = 0.0
    page_depth: float = 0.0
    avg_visit_duration: float = 0.0


@dataclass
class TrafficTrend:
    """Тренд (дельта % к предыдущему периоду)."""
    visits_delta_pct: float = 0.0
    users_delta_pct: float = 0.0
    bounce_rate_delta_pct: float = 0.0
    page_depth_delta_pct: float = 0.0
    avg_visit_duration_delta_pct: float = 0.0


@dataclass
class TrafficSource:
    """Источник трафика."""
    source: str
    visits: int = 0
    users: int = 0
    bounce_rate: float = 0.0


@dataclass
class GoalStats:
    """Статистика по цели."""
    id: str
    name: str
    reaches: int = 0
    cr: float = 0.0


@dataclass
class BitrixTask:
    """Задача Bitrix24."""
    id: str
    title: str
    status: str
    responsible_id: str = ""
    creator_id: str = ""
    deadline: str = ""
    closed_date: str = ""


@dataclass
class MetricaData:
    """Данные Метрики."""
    summary: TrafficSummary = field(default_factory=TrafficSummary)
    trend: TrafficTrend = field(default_factory=TrafficTrend)
    sources: List[TrafficSource] = field(default_factory=list)
    goals: List[GoalStats] = field(default_factory=list)


@dataclass
class BitrixData:
    """Данные Bitrix24."""
    tasks_active_count: int = 0
    tasks_by_status: Dict[str, int] = field(default_factory=dict)
    tasks_overdue: List[BitrixTask] = field(default_factory=list)
    tasks_recently_completed: List[BitrixTask] = field(default_factory=list)


@dataclass
class ProjectOverviewData:
    """Полные данные обзора проекта."""
    project: ProjectInfo
    period_from: str
    period_to: str
    metrica: MetricaData = field(default_factory=MetricaData)
    bitrix: BitrixData = field(default_factory=BitrixData)
    errors: List[str] = field(default_factory=list)
