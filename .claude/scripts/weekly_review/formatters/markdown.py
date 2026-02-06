"""Форматтер для вывода отчёта в markdown."""

from datetime import datetime
from typing import List

from ..models import (
    WeeklyReportData,
    Task,
    Meeting,
    DialogSummary,
    GitActivity,
)
from ..date_utils import format_date_range


class MarkdownFormatter:
    """Форматтер отчёта в markdown."""

    def format_report(self, data: WeeklyReportData) -> str:
        """
        Отформатировать полный отчёт.

        Args:
            data: Данные еженедельного отчёта

        Returns:
            Markdown текст отчёта
        """
        sections = []

        # Заголовок
        sections.append(self._format_header(data))

        # Задачи
        tasks_section = self._format_tasks(data)
        if tasks_section:
            sections.append(tasks_section)

        # Встречи
        meetings_section = self._format_meetings(data.meetings)
        if meetings_section:
            sections.append(meetings_section)

        # Переписки
        chats_section = self._format_chats(data.chat_summaries)
        if chats_section:
            sections.append(chats_section)

        # Трудозатраты
        time_section = self._format_time_tracking(data)
        if time_section:
            sections.append(time_section)

        # Git активность
        git_section = self._format_git_activity(data.git_activity)
        if git_section:
            sections.append(git_section)

        return "\n\n".join(sections)

    def _format_header(self, data: WeeklyReportData) -> str:
        """Заголовок отчёта."""
        period = format_date_range(data.date_from, data.date_to)
        return f"# Обзор недели: {period}\n\nПользователь: **{data.user_name}**"

    def _format_tasks(self, data: WeeklyReportData) -> str:
        """Секция задач."""
        lines = ["## Задачи"]

        # Статистика
        stats = []
        if data.tasks_created:
            stats.append(f"**Создано:** {len(data.tasks_created)}")
        if data.tasks_assigned:
            stats.append(f"**Назначено:** {len(data.tasks_assigned)}")
        if data.tasks_closed:
            stats.append(f"**Закрыто:** {len(data.tasks_closed)}")
        if data.tasks_active:
            stats.append(f"**Активных:** {len(data.tasks_active)}")

        if stats:
            lines.append(" | ".join(stats))

        # Созданные задачи
        if data.tasks_created:
            lines.append("\n### Созданные задачи")
            for task in data.tasks_created[:10]:  # Топ 10
                lines.append(f"- [{task.id}] {task.title}")

        # Закрытые задачи
        if data.tasks_closed:
            lines.append("\n### Закрытые задачи")
            for task in data.tasks_closed[:10]:  # Топ 10
                lines.append(f"- [{task.id}] {task.title}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def _format_meetings(self, meetings: List[Meeting]) -> str:
        """Секция встреч."""
        if not meetings:
            return ""

        lines = [f"## Встречи ({len(meetings)})"]

        for meeting in meetings:
            date_str = meeting.date_from.strftime("%d.%m %H:%M")
            lines.append(f"\n### {meeting.name}")
            lines.append(f"**Дата:** {date_str}")

            if meeting.attendees:
                attendees = ", ".join(meeting.attendees[:5])
                if len(meeting.attendees) > 5:
                    attendees += f" и ещё {len(meeting.attendees) - 5}"
                lines.append(f"**Участники:** {attendees}")

            if meeting.location:
                lines.append(f"**Место:** {meeting.location}")

        return "\n".join(lines)

    def _format_chats(self, summaries: List[DialogSummary]) -> str:
        """Секция переписок."""
        if not summaries:
            return ""

        lines = [f"## Ключевые переписки ({len(summaries)})"]

        for summary in summaries:
            lines.append(f"\n### {summary.dialog_name}")
            lines.append(f"**Сообщений:** {summary.message_count}")
            lines.append(f"**Тема:** {summary.topic}")

            if summary.agreements:
                lines.append("\n**Договорённости:**")
                for agreement in summary.agreements:
                    lines.append(f"- {agreement}")

            if summary.decisions:
                lines.append("\n**Решения:**")
                for decision in summary.decisions:
                    lines.append(f"- {decision}")

            if summary.questions:
                lines.append("\n**Открытые вопросы:**")
                for question in summary.questions:
                    lines.append(f"- {question}")

            if summary.awaits_response:
                lines.append("\n⚠️ **Ожидает вашей реакции**")

        return "\n".join(lines)

    def _format_time_tracking(self, data: WeeklyReportData) -> str:
        """Секция трудозатрат."""
        if not data.time_entries:
            return ""

        total_hours = data.total_time_spent

        lines = [
            "## Трудозатраты",
            f"**Всего списано времени:** {total_hours:.1f} ч",
        ]

        # Сгруппировать по задачам
        task_times = {}
        for entry in data.time_entries:
            task_times[entry.task_id] = task_times.get(entry.task_id, 0.0) + entry.hours

        # Топ задач по времени
        sorted_tasks = sorted(task_times.items(), key=lambda x: x[1], reverse=True)

        if sorted_tasks:
            lines.append("\n### Топ задач по времени")
            for task_id, hours in sorted_tasks[:10]:
                # Найти название задачи
                task_title = self._find_task_title(task_id, data)
                lines.append(f"- [{task_id}] {task_title}: **{hours:.1f} ч**")

        return "\n".join(lines)

    def _find_task_title(self, task_id: str, data: WeeklyReportData) -> str:
        """Найти название задачи по ID."""
        all_tasks = (
            data.tasks_created +
            data.tasks_assigned +
            data.tasks_closed +
            data.tasks_active
        )

        for task in all_tasks:
            if task.id == task_id:
                return task.title

        return "Задача не найдена"

    def _format_git_activity(self, activities: List[GitActivity]) -> str:
        """Секция git активности."""
        if not activities:
            return ""

        lines = [f"## Проекты (локальная разработка) — {len(activities)}"]

        for activity in activities:
            lines.append(f"\n### {activity.project_name}")
            lines.append(
                f"**Коммитов:** {len(activity.commits)} | "
                f"**Файлов:** {activity.files_changed} | "
                f"**+{activity.insertions}/-{activity.deletions}**"
            )

            # Группировать коммиты по смыслу (упростить)
            if activity.commits:
                lines.append("\n**Что сделано:**")
                # Показать до 5 коммитов
                for commit in activity.commits[:5]:
                    msg = commit["message"][:100]
                    lines.append(f"- {msg}")

                if len(activity.commits) > 5:
                    lines.append(f"- ... и ещё {len(activity.commits) - 5} коммитов")

        return "\n".join(lines)
