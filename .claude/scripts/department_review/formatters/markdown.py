"""Markdown formatter for department review report."""

from __future__ import annotations

from models import DepartmentReport
from utils import format_period


def format_report(report: DepartmentReport) -> str:
    totals = report.totals()
    lines: list[str] = []

    lines.append(f"## Отчёт по отделу: {report.department.name}")
    lines.append("")
    lines.append(f"Период: {format_period(report.date_from, report.date_to)}")
    lines.append(f"Руководитель: {report.manager_name}")
    lines.append("")
    lines.append("### Итого по отделу")
    lines.append(f"- Сотрудников: {totals['employees']}")
    lines.append(f"- Задач создано: {totals['created']}")
    lines.append(f"- Задач закрыто: {totals['closed']}")
    lines.append(f"- Просроченных задач: {totals['overdue']}")
    lines.append(f"- Встреч: {totals['meetings']}")
    lines.append(f"- Сообщений в личках: {totals['dm_messages']}")
    lines.append(f"- Сообщений в общих чатах: {totals['shared_messages']}")
    lines.append("")

    if not report.employees:
        lines.append("Сотрудники для выбранного отдела не найдены.")
        return "\n".join(lines)

    lines.append("### По сотрудникам")
    lines.append("| Сотрудник | Создал | Закрыл | Просрочено | Встречи | Лички | Общие чаты |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for employee in report.employees:
        shared = f"{employee.chats.shared_chat_dialogs}/{employee.chats.shared_chat_messages}"
        lines.append(
            f"| {employee.name} | {employee.tasks.created} | {employee.tasks.closed} | "
            f"{employee.tasks.overdue} | {employee.meetings_count} | {employee.chats.dm_messages} | {shared} |"
        )
    lines.append("")

    risks = []
    for employee in report.employees:
        if employee.tasks.overdue > 0:
            risks.append(f"{employee.name}: просрочено {employee.tasks.overdue}")
    inactive = []
    for employee in report.employees:
        total_activity = (
            employee.tasks.created
            + employee.tasks.closed
            + employee.meetings_count
            + employee.chats.dm_messages
            + employee.chats.shared_chat_messages
        )
        if total_activity == 0:
            inactive.append(employee.name)

    if risks or inactive:
        lines.append("### Риски и внимание")
        for risk in risks:
            lines.append(f"- {risk}")
        for name in inactive:
            lines.append(f"- Нет активности за период: {name}")
        lines.append("")

    all_warnings = list(report.warnings)
    for employee in report.employees:
        for warning in employee.warnings:
            all_warnings.append(f"{employee.name}: {warning}")

    if all_warnings:
        lines.append("### Технические предупреждения")
        for warning in all_warnings:
            lines.append(f"- {warning}")

    return "\n".join(lines)

