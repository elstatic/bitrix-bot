"""Data models for department review report."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any


@dataclass
class DepartmentInfo:
    id: str
    name: str


@dataclass
class TaskMetrics:
    created: int = 0
    closed: int = 0
    overdue: int = 0


@dataclass
class ChatMetrics:
    dm_dialogs: int = 0
    dm_messages: int = 0
    shared_chat_dialogs: int = 0
    shared_chat_messages: int = 0


@dataclass
class EmployeeMetrics:
    id: str
    name: str
    work_position: str = ""
    tasks: TaskMetrics = field(default_factory=TaskMetrics)
    meetings_count: int = 0
    chats: ChatMetrics = field(default_factory=ChatMetrics)
    warnings: List[str] = field(default_factory=list)


@dataclass
class DepartmentReport:
    manager_id: str
    manager_name: str
    department: DepartmentInfo
    date_from: datetime
    date_to: datetime
    employees: List[EmployeeMetrics] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def totals(self) -> Dict[str, int]:
        return {
            "employees": len(self.employees),
            "created": sum(e.tasks.created for e in self.employees),
            "closed": sum(e.tasks.closed for e in self.employees),
            "overdue": sum(e.tasks.overdue for e in self.employees),
            "meetings": sum(e.meetings_count for e in self.employees),
            "dm_messages": sum(e.chats.dm_messages for e in self.employees),
            "shared_messages": sum(e.chats.shared_chat_messages for e in self.employees),
        }

    def to_dict(self) -> Dict[str, Any]:
        totals = self.totals()
        employees = []
        for item in self.employees:
            employees.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "work_position": item.work_position,
                    "tasks": {
                        "created": item.tasks.created,
                        "closed": item.tasks.closed,
                        "overdue": item.tasks.overdue,
                    },
                    "meetings_count": item.meetings_count,
                    "chats": {
                        "dm_dialogs": item.chats.dm_dialogs,
                        "dm_messages": item.chats.dm_messages,
                        "shared_chat_dialogs": item.chats.shared_chat_dialogs,
                        "shared_chat_messages": item.chats.shared_chat_messages,
                    },
                    "warnings": item.warnings,
                }
            )

        return {
            "manager": {"id": self.manager_id, "name": self.manager_name},
            "department": {"id": self.department.id, "name": self.department.name},
            "period": {
                "date_from": self.date_from.strftime("%Y-%m-%d"),
                "date_to": self.date_to.strftime("%Y-%m-%d"),
            },
            "totals": totals,
            "employees": employees,
            "warnings": self.warnings,
        }

