"""Модели данных для weekly review."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Task:
    """Задача из Bitrix24."""
    id: str
    title: str
    status: str
    responsible_id: str
    creator_id: str
    created_date: datetime
    closed_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    time_spent: float = 0.0  # в часах


@dataclass
class Meeting:
    """Встреча из календаря."""
    id: str
    name: str
    date_from: datetime
    date_to: datetime
    attendees: list[str] = field(default_factory=list)
    location: str = ""


@dataclass
class DialogSummary:
    """Суммаризация диалога."""
    dialog_id: str
    dialog_name: str
    message_count: int
    topic: str
    agreements: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    awaits_response: bool = False


@dataclass
class TimeEntry:
    """Запись трудозатрат."""
    task_id: str
    user_id: str
    seconds: int
    comment: str
    created_date: datetime

    @property
    def hours(self) -> float:
        """Время в часах."""
        return round(self.seconds / 3600, 2)


@dataclass
class GitActivity:
    """Активность в git репозитории."""
    project_name: str
    project_path: str
    commits: list[dict] = field(default_factory=list)
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


@dataclass
class WeeklyReportData:
    """Собранные данные для еженедельного отчёта."""
    user_id: str
    user_name: str
    date_from: datetime
    date_to: datetime

    # Задачи
    tasks_created: list[Task] = field(default_factory=list)
    tasks_assigned: list[Task] = field(default_factory=list)
    tasks_closed: list[Task] = field(default_factory=list)
    tasks_active: list[Task] = field(default_factory=list)

    # Встречи
    meetings: list[Meeting] = field(default_factory=list)

    # Переписки
    chat_summaries: list[DialogSummary] = field(default_factory=list)

    # Трудозатраты
    time_entries: list[TimeEntry] = field(default_factory=list)

    # Git активность
    git_activity: list[GitActivity] = field(default_factory=list)

    @property
    def total_time_spent(self) -> float:
        """Суммарное время по трудозатратам в часах."""
        return sum(entry.hours for entry in self.time_entries)
