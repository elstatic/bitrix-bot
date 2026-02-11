#!/usr/bin/env python3
"""
Daily Review - быстрый сбор данных за день.

Оптимизации:
- Batch API Bitrix24
- Параллельные запросы
- Кеширование чатов
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Добавить директорию скрипта в sys.path для абсолютных импортов
SCRIPT_DIR = Path(__file__).resolve().parent
WEEKLY_DIR = SCRIPT_DIR.parent / "weekly_review"
sys.path.insert(0, str(WEEKLY_DIR))

from api.bitrix_client import BitrixClient  # type: ignore
from api.batch_builder import BatchRequestBuilder  # type: ignore
from date_utils import parse_bitrix_datetime, format_bitrix_date_filter  # type: ignore

from config import load_config
from cache import JsonCache


@dataclass
class Period:
    date_from: datetime
    date_to: datetime

    @property
    def key(self) -> str:
        return f"{self.date_from.strftime('%Y-%m-%d')}_{self.date_to.strftime('%Y-%m-%d')}"


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d")


def resolve_period(args: argparse.Namespace) -> Period:
    if args.date:
        day = _parse_date(args.date)
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = day.replace(hour=23, minute=59, second=59, microsecond=0)
        return Period(start, end)

    if args.date_from and args.date_to:
        start = _parse_date(args.date_from).replace(hour=0, minute=0, second=0, microsecond=0)
        end = _parse_date(args.date_to).replace(hour=23, minute=59, second=59, microsecond=0)
        return Period(start, end)

    if args.yesterday:
        day = datetime.now().date() - timedelta(days=1)
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time()).replace(microsecond=0)
        return Period(start, end)

    raise ValueError("Нужно указать --date YYYY-MM-DD или --from/--to или --yesterday")


def build_batch_commands(
    user_id: str,
    period: Period,
) -> Dict[str, str]:
    from_str = format_bitrix_date_filter(period.date_from)
    to_str = format_bitrix_date_filter(period.date_to)

    builder = BatchRequestBuilder()

    builder.add_task_list(
        "tasks_created",
        filters={
            "CREATED_BY": user_id,
            ">=CREATED_DATE": from_str,
            "<=CREATED_DATE": to_str,
        },
    )

    builder.add_task_list(
        "tasks_assigned",
        filters={
            "RESPONSIBLE_ID": user_id,
            ">=CREATED_DATE": from_str,
            "<=CREATED_DATE": to_str,
            "!CREATED_BY": user_id,
        },
    )

    builder.add_task_list(
        "tasks_closed",
        filters={
            "RESPONSIBLE_ID": user_id,
            "STATUS": "5",
            ">=CLOSED_DATE": from_str,
            "<=CLOSED_DATE": to_str,
        },
    )

    builder.add_task_list(
        "tasks_deadlines",
        filters={
            "RESPONSIBLE_ID": user_id,
            "!STATUS": "5",
            ">=DEADLINE": from_str,
            "<=DEADLINE": to_str,
        },
    )

    builder.add_calendar_events(
        "calendar",
        user_id=user_id,
        date_from=period.date_from,
        date_to=period.date_to,
    )

    commands = builder.build()
    commands["profile"] = "profile"
    return commands


def _filter_recent_items(items: List[Dict[str, Any]], period: Period) -> List[Dict[str, Any]]:
    result = []
    for item in items:
        title = (item.get("title") or "").lower()
        if "уведомления" in title or "notifications" in title:
            continue
        if item.get("type") == "notification":
            continue

        date_last = item.get("date_last_activity") or item.get("date_message")
        if date_last:
            try:
                dt = parse_bitrix_datetime(date_last)
                if dt and dt < period.date_from:
                    continue
            except Exception:
                pass

        result.append(item)
    return result


async def fetch_dialog_messages(
    client: BitrixClient,
    dialog_id: str,
    period: Period,
    max_pages: int,
    max_pages_when_empty: int,
    semaphore: asyncio.Semaphore,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    messages_in_period: List[Dict[str, Any]] = []
    users_map: Dict[str, str] = {}

    last_id = None
    pages = 0
    first_page_all_in_period = False

    while pages < max_pages:
        params = {"DIALOG_ID": dialog_id, "LIMIT": 20}
        if last_id is not None:
            params["LAST_ID"] = last_id

        async with semaphore:
            resp = await client.call("im.dialog.messages.get", params)

        if not resp:
            break

        msgs = resp.get("messages", []) or []
        users = resp.get("users", []) or []
        for u in users:
            uid = str(u.get("id"))
            name = u.get("name") or u.get("first_name") or u.get("last_name")
            if uid and name:
                users_map[uid] = name

        if not msgs:
            break

        # Фильтрация по дате
        in_period = []
        all_in_period = True
        for msg in msgs:
            date_str = msg.get("date")
            if not date_str:
                all_in_period = False
                continue
            try:
                dt = parse_bitrix_datetime(date_str)
            except Exception:
                all_in_period = False
                continue

            if dt and period.date_from <= dt <= period.date_to:
                in_period.append(msg)
            else:
                all_in_period = False

        messages_in_period.extend(in_period)

        # Логика пагинации
        if pages == 0 and not messages_in_period:
            # Если в первой странице нет сообщений за период — ищем глубже, но не более max_pages_when_empty
            last_id = msgs[-1].get("id")
            pages += 1
            if pages >= max_pages_when_empty:
                break
            continue

        if pages == 0 and all_in_period:
            first_page_all_in_period = True

        if first_page_all_in_period and pages + 1 < max_pages:
            last_id = msgs[-1].get("id")
            pages += 1
            continue

        break

    return messages_in_period, users_map


async def collect_chat_digest(
    client: BitrixClient,
    period: Period,
    chat_limit: int,
    top_limit: int,
    max_pages: int,
    cache: JsonCache,
) -> Dict[str, Any]:
    cache_key = f"{period.key}_cl{chat_limit}_tl{top_limit}_mp{max_pages}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    recent = await client.call("im.recent.list", {"SKIP_OPENLINES": "Y"})
    items = recent.get("items", []) if isinstance(recent, dict) else []

    filtered = _filter_recent_items(items, period)

    # Приоритет: личные диалоги, затем групповые
    filtered.sort(key=lambda x: 0 if x.get("type") == "user" else 1)
    filtered = filtered[:chat_limit]

    semaphore = asyncio.Semaphore(5)

    tasks = []
    for item in filtered:
        dialog_id = item.get("id")
        tasks.append(
            fetch_dialog_messages(
                client,
                str(dialog_id),
                period,
                max_pages=max_pages,
                max_pages_when_empty=3,
                semaphore=semaphore,
            )
        )

    results = await asyncio.gather(*tasks)

    dialogs = []
    for item, (messages, users_map) in zip(filtered, results):
        if not messages:
            continue
        dialogs.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "type": item.get("type"),
                "messages": messages,
                "users": users_map,
            }
        )

    dialogs.sort(key=lambda d: (0 if d.get("type") == "user" else 1, -len(d.get("messages", []))))
    dialogs = dialogs[:top_limit]

    payload = {"count": len(dialogs), "dialogs": dialogs}
    cache.set(cache_key, payload)
    return payload


async def collect_git_activity(projects_dirs: str, period: Period, cache_file: Path) -> List[Dict[str, Any]]:
    # Поддержка нескольких директорий через ':'
    roots = [Path(p).expanduser() for p in projects_dirs.split(":" ) if p.strip()]
    roots = [p for p in roots if p.exists()]

    if not roots:
        return []

    # Кеш списка проектов
    projects_by_root: Dict[str, List[str]] = {}
    cache_valid = False
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text())
            cache_time = datetime.fromisoformat(cached.get("timestamp"))
            age = (datetime.now() - cache_time).total_seconds()
            if age < 86400:
                projects_by_root = cached.get("projects_by_root", {})
                cache_valid = True
        except Exception:
            cache_valid = False

    if not cache_valid:
        for root in roots:
            repos = []
            for base, dirs, _ in os.walk(root):
                base_path = Path(base)
                if ".git" in dirs:
                    repos.append(str(base_path))
                    dirs[:] = []
                    continue
                # ограничение глубины: до 2 уровней от root
                try:
                    rel = base_path.relative_to(root)
                    if len(rel.parts) >= 2:
                        dirs[:] = []
                except Exception:
                    continue
            projects_by_root[str(root)] = repos

        cache_file.write_text(
            json.dumps(
                {
                    "timestamp": datetime.now().isoformat(),
                    "projects_by_root": projects_by_root,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    projects = []
    for repo_list in projects_by_root.values():
        projects.extend(repo_list)

    if not projects:
        return []

    semaphore = asyncio.Semaphore(6)

    async def analyze_repo(repo_path: str) -> Optional[Dict[str, Any]]:
        since = period.date_from.strftime("%Y-%m-%d")
        until = (period.date_to + timedelta(days=1)).strftime("%Y-%m-%d")

        log_cmd = [
            "git",
            "-C",
            repo_path,
            "log",
            f"--after={since}",
            f"--before={until}",
            "--pretty=format:%H|%s|%ai",
            "--no-merges",
        ]

        async with semaphore:
            process = await asyncio.create_subprocess_exec(
                *log_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()

        if process.returncode != 0:
            return None

        lines = stdout.decode("utf-8").strip().split("\n")
        commits = []
        for line in lines:
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

        return {
            "repo": repo_path,
            "project": Path(repo_path).name,
            "commit_count": len(commits),
            "commits": commits,
        }

    results = await asyncio.gather(*[analyze_repo(p) for p in projects])
    return [r for r in results if r]


async def collect_all(args: argparse.Namespace) -> Dict[str, Any]:
    config = load_config()
    period = resolve_period(args)

    async with BitrixClient(config.bitrix_webhook_url, debug=args.debug) as client:
        # Профиль (для user_id) через batch
        commands = {"profile": "profile"}
        profile_result = await client.batch(commands)
        profile = profile_result.get("profile", {}) if profile_result else {}
        user_id = str(profile.get("ID", ""))

        if not user_id:
            # fallback: одиночный запрос
            profile = await client.call("profile") or {}
            user_id = str(profile.get("ID", ""))

        if not user_id:
            raise ValueError("Не удалось получить ID пользователя через profile")

        # Batch: задачи + календарь + профиль
        batch_commands = build_batch_commands(user_id, period)
        batch_result = await client.batch(batch_commands)

        tasks_created = batch_result.get("tasks_created", {}).get("tasks", []) if batch_result else []
        tasks_assigned = batch_result.get("tasks_assigned", {}).get("tasks", []) if batch_result else []
        tasks_closed = batch_result.get("tasks_closed", {}).get("tasks", []) if batch_result else []
        tasks_deadlines = batch_result.get("tasks_deadlines", {}).get("tasks", []) if batch_result else []
        calendar_events = batch_result.get("calendar", []) if batch_result else []

        # Чаты и git — параллельно
        chat_cache = JsonCache(config.chat_cache_dir, ttl_seconds=86400)
        chat_task = collect_chat_digest(
            client,
            period,
            chat_limit=args.chat_limit,
            top_limit=args.top_limit,
            max_pages=args.max_pages,
            cache=chat_cache,
        )
        git_task = collect_git_activity(config.projects_dirs, period, config.projects_cache_file)

        chats, git_activity = await asyncio.gather(chat_task, git_task)

        return {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "date_from": period.date_from.strftime("%Y-%m-%d"),
                "date_to": period.date_to.strftime("%Y-%m-%d"),
                "user": {
                    "id": profile.get("ID"),
                    "name": f"{profile.get('NAME', '')} {profile.get('LAST_NAME', '')}".strip(),
                },
            },
            "tasks": {
                "created": tasks_created,
                "assigned": tasks_assigned,
                "closed": tasks_closed,
                "deadlines": tasks_deadlines,
            },
            "meetings": calendar_events,
            "chats": chats,
            "git": git_activity,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily Review collector")
    parser.add_argument("--date", help="Дата YYYY-MM-DD")
    parser.add_argument("--from", dest="date_from", help="Дата начала YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", help="Дата окончания YYYY-MM-DD")
    parser.add_argument("--yesterday", action="store_true", help="Использовать вчерашнюю дату")
    parser.add_argument("--chat-limit", type=int, default=20, help="Лимит диалогов")
    parser.add_argument("--top-limit", type=int, default=15, help="Топ диалогов для дайджеста")
    parser.add_argument("--max-pages", type=int, default=5, help="Макс. страниц сообщений на диалог")
    parser.add_argument("--format", choices=["json"], default="json")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    try:
        data = asyncio.run(collect_all(args))
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
