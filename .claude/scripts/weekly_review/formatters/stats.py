"""Расчёт статистики для отчёта."""

from typing import Dict, Any
from ..models import WeeklyReportData


class StatsCalculator:
    """Калькулятор статистики."""

    @staticmethod
    def calculate_stats(data: WeeklyReportData) -> Dict[str, Any]:
        """
        Рассчитать статистику по отчёту.

        Args:
            data: Данные отчёта

        Returns:
            Словарь со статистикой
        """
        return {
            "tasks": {
                "created": len(data.tasks_created),
                "assigned": len(data.tasks_assigned),
                "closed": len(data.tasks_closed),
                "active": len(data.tasks_active),
            },
            "meetings": {
                "total": len(data.meetings),
            },
            "chats": {
                "total": len(data.chat_summaries),
                "awaits_response": sum(
                    1 for s in data.chat_summaries if s.awaits_response
                ),
            },
            "time_tracking": {
                "total_hours": data.total_time_spent,
                "entries_count": len(data.time_entries),
            },
            "git": {
                "projects": len(data.git_activity),
                "total_commits": sum(len(a.commits) for a in data.git_activity),
                "total_files": sum(a.files_changed for a in data.git_activity),
                "total_insertions": sum(a.insertions for a in data.git_activity),
                "total_deletions": sum(a.deletions for a in data.git_activity),
            },
        }
