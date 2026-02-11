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
from typing import Any, Dict, List, Optional, Tuple, Iterable

# Добавить директории в sys.path для абсолютных импортов
SCRIPT_DIR = Path(__file__).resolve().parent
WEEKLY_DIR = SCRIPT_DIR.parent / "weekly_review"
# Сначала текущая папка (daily_review), затем weekly_review
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(1, str(WEEKLY_DIR))

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


def _chunked(items: List[str], size: int) -> List[List[str]]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def _extract_task_ids(tasks: List[Dict[str, Any]]) -> List[str]:
    ids = []
    for t in tasks:
        task_id = t.get("id") or t.get("ID")
        if task_id:
            ids.append(str(task_id))
    return ids


def _get_task_chat_id(task: Dict[str, Any]) -> Optional[str]:
    # Try common field names observed in Bitrix24 API
    for key in ("chatId", "CHAT_ID", "IM_CHAT_ID", "UF_CHAT_ID"):
        val = task.get(key)
        if val:
            return str(val)
    return None


async def list_active_task_ids_for_user(client: BitrixClient, user_id: str) -> List[str]:
    task_ids: set[str] = set()

    async def fetch(filters: Dict[str, Any]):
        params = {"filter": filters, "select": ["ID"]}
        items = await client.paginated_call("tasks.task.list", params, max_pages=10)
        for item in items:
            task_id = item.get("id") or item.get("ID")
            if task_id:
                task_ids.add(str(task_id))

    await fetch({"RESPONSIBLE_ID": user_id, "!STATUS": "5"})
    await fetch({"CREATED_BY": user_id, "!STATUS": "5"})
    return list(task_ids)


async def collect_task_chat_dialogs(
    client: BitrixClient,
    period: Period,
    task_ids: List[str],
    max_pages: int,
) -> List[Dict[str, Any]]:
    if not task_ids:
        return []

    dialogs: List[Dict[str, Any]] = []
    semaphore = asyncio.Semaphore(5)

    for chunk in _chunked(task_ids, 50):
        commands = {f"task_{tid}": f"tasks.task.get?taskId={tid}" for tid in chunk}
        result = await client.batch(commands)
        if not result:
            continue

        tasks = []
        for value in result.values():
            if isinstance(value, dict) and "task" in value:
                tasks.append(value["task"])

        fetch_tasks = []
        fallback_tasks = []
        for task in tasks:
            title = task.get("title") or task.get("TITLE") or f"Задача {task.get('id', '')}".strip()
            chat_id = _get_task_chat_id(task)
            if chat_id:
                dialog_id = f"chat{chat_id}"
                fetch_tasks.append((dialog_id, title))
            else:
                task_id = str(task.get("id") or task.get("ID") or "")
                if task_id:
                    fallback_tasks.append((task_id, title))

        # IM-чаты задач
        if fetch_tasks:
            message_tasks = [
                fetch_dialog_messages(
                    client,
                    dialog_id,
                    period,
                    max_pages=max_pages,
                    max_pages_when_empty=3,
                    semaphore=semaphore,
                )
                for dialog_id, _ in fetch_tasks
            ]

            results = await asyncio.gather(*message_tasks)
            for (dialog_id, title), (messages, users_map) in zip(fetch_tasks, results):
                if not messages:
                    continue
                dialogs.append(
                    {
                        "id": dialog_id,
                        "title": f"Задача: {title}",
                        "type": "chat",
                        "messages": messages,
                        "users": users_map,
                    }
                )

        # fallback: комментарии задач (task.commentitem.getlist)
        if fallback_tasks:
            comment_tasks = [fetch_task_comments(client, task_id, period) for task_id, _ in fallback_tasks]
            comment_results = await asyncio.gather(*comment_tasks)
            for (task_id, title), (messages, users_map) in zip(fallback_tasks, comment_results):
                if not messages:
                    continue
                dialogs.append(
                    {
                        "id": f"task{task_id}",
                        "title": f"Задача: {title}",
                        "type": "task_comments",
                        "messages": messages,
                        "users": users_map,
                    }
                )

    return dialogs


def merge_dialogs(base: Dict[str, Any], extra: List[Dict[str, Any]]) -> Dict[str, Any]:
    dialogs = base.get("dialogs", [])
    seen = {str(d.get("id")) for d in dialogs}
    for d in extra:
        if str(d.get("id")) in seen:
            continue
        dialogs.append(d)
        seen.add(str(d.get("id")))
    base["dialogs"] = dialogs
    base["count"] = len(dialogs)
    return base


async def list_active_tasks_for_user(client: BitrixClient, user_id: str) -> Dict[str, str]:
    tasks: Dict[str, str] = {}

    async def fetch(filter_params: Dict[str, Any]):
        params = {
            "filter": filter_params,
            "select": ["ID", "TITLE"],
        }
        items = await client.paginated_call("tasks.task.list", params, max_pages=10)
        for item in items:
            task_id = item.get("id") or item.get("ID")
            if task_id:
                tasks[str(task_id)] = item.get("title") or item.get("TITLE") or f"Задача {task_id}"

    # Активные задачи пользователя как ответственного
    await fetch({"RESPONSIBLE_ID": user_id, "!STATUS": "5"})
    # Активные задачи, созданные пользователем
    await fetch({"CREATED_BY": user_id, "!STATUS": "5"})

    return tasks


def _iter_task_ids(tasks_map: Dict[str, str]) -> Iterable[str]:
    return tasks_map.keys()


async def fetch_task_comments(
    client: BitrixClient,
    task_id: str,
    period: Period,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Fetch task comments for a task and filter by period."""
    # Method accepts TASKID; return list of comments
    resp = await client.call("task.commentitem.getlist", {"TASKID": task_id})
    if not resp:
        return [], {}

    comments = resp if isinstance(resp, list) else resp.get("COMMENTS", resp.get("result", []))
    messages: List[Dict[str, Any]] = []
    users_map: Dict[str, str] = {}
    for c in comments or []:
        date_str = c.get("POST_DATE") or c.get("DATE_CREATE") or c.get("POST_DATE_TS")
        if not date_str:
            continue
        try:
            dt = parse_bitrix_datetime(date_str)
        except Exception:
            continue
        if not (period.date_from <= dt <= period.date_to):
            continue
        author_id = c.get("AUTHOR_ID") or c.get("AUTHOR_ID".lower())
        author_name = c.get("AUTHOR_NAME") or c.get("AUTHOR_NAME".lower())
        if author_id and author_name:
            users_map[str(author_id)] = author_name
        messages.append(
            {
                "id": c.get("ID"),
                "author_id": author_id,
                "date": date_str,
                "text": c.get("POST_MESSAGE") or c.get("MESSAGE") or "",
            }
        )
    return messages, users_map


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


TODAY_CACHE_TTL = 300  # 5 минут


async def collect_chat_digest(
    client: BitrixClient,
    period: Period,
    chat_limit: int,
    top_limit: int,
    max_pages: int,
    cache: JsonCache,
) -> Dict[str, Any]:
    cache_key = f"{period.key}_cl{chat_limit}_tl{top_limit}_mp{max_pages}"
    is_today = period.date_from.date() == datetime.now().date() and period.date_to.date() == datetime.now().date()

    # Проверка кеша: для прошлых дат — стандартный TTL, для сегодня — короткий
    if is_today:
        cached = cache.get_if_fresh(cache_key, TODAY_CACHE_TTL)
    else:
        cached = cache.get(cache_key)
    if cached is not None:
        return cached

    # im.recent.list — всегда вызываем (1 лёгкий запрос)
    recent = await client.call("im.recent.list", {"SKIP_OPENLINES": "Y"})
    items = recent.get("items", []) if isinstance(recent, dict) else []

    filtered = _filter_recent_items(items, period)

    # Приоритет: личные диалоги, затем групповые
    filtered.sort(key=lambda x: 0 if x.get("type") == "user" else 1)
    filtered = filtered[:chat_limit]

    # Инкрементальный кеш: для «сегодня» загрузить старый кеш (даже с истёкшим TTL)
    # и дозагрузить только изменённые диалоги
    cached_dialog_activity: Dict[str, str] = {}
    cached_dialogs_map: Dict[str, Dict[str, Any]] = {}
    if is_today:
        stale_cached = cache.get_if_fresh(cache_key, 86400)  # читаем за последние сутки
        if stale_cached and isinstance(stale_cached, dict):
            cached_dialog_activity = stale_cached.get("dialog_activity", {})
            for d in stale_cached.get("dialogs", []):
                did = str(d.get("id"))
                if did:
                    cached_dialogs_map[did] = d

    # Определить, какие диалоги нужно загрузить
    to_fetch: List[Dict[str, Any]] = []
    from_cache: List[Dict[str, Any]] = []

    for item in filtered:
        dialog_id = str(item.get("id"))
        current_activity = item.get("date_last_activity") or item.get("date_message") or ""

        if (
            dialog_id in cached_dialogs_map
            and dialog_id in cached_dialog_activity
            and cached_dialog_activity[dialog_id] == current_activity
        ):
            from_cache.append(cached_dialogs_map[dialog_id])
        else:
            to_fetch.append(item)

    # Загрузить только изменённые диалоги
    semaphore = asyncio.Semaphore(5)
    tasks = []
    for item in to_fetch:
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

    fetched_dialogs = []
    for item, (messages, users_map) in zip(to_fetch, results):
        if not messages:
            continue
        fetched_dialogs.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "type": item.get("type"),
                "messages": messages,
                "users": users_map,
            }
        )

    # Объединить кешированные и свежие
    dialogs = from_cache + fetched_dialogs

    dialogs.sort(key=lambda d: (0 if d.get("type") == "user" else 1, -len(d.get("messages", []))))
    if not is_today:
        dialogs = dialogs[:top_limit]

    # Построить dialog_activity для будущего сравнения
    dialog_activity: Dict[str, str] = {}
    for item in filtered:
        did = str(item.get("id"))
        activity = item.get("date_last_activity") or item.get("date_message") or ""
        dialog_activity[did] = activity

    payload = {"count": len(dialogs), "dialogs": dialogs, "dialog_activity": dialog_activity}
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
        since = period.date_from.strftime("%Y-%m-%d 00:00:00")
        until = period.date_to.strftime("%Y-%m-%d 23:59:59")

        log_cmd = [
            "git",
            "-C",
            repo_path,
            "log",
            f"--since={since}",
            f"--until={until}",
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
            # fallback: parse user id from webhook URL (/rest/<id>/)
            import re
            match = re.search(r"/rest/(\d+)/", client.webhook_url + "/")
            if match:
                user_id = match.group(1)
                if not profile:
                    profile = {"ID": user_id, "NAME": "User", "LAST_NAME": user_id}
            else:
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

        # Подмешать чаты задач (все активные задачи пользователя + задачи за период)
        active_tasks = await list_active_tasks_for_user(client, user_id)
        task_ids = list({
            *_iter_task_ids(active_tasks),
            *_extract_task_ids(tasks_created),
            *_extract_task_ids(tasks_assigned),
            *_extract_task_ids(tasks_closed),
            *_extract_task_ids(tasks_deadlines),
        })
        task_chat_dialogs = await collect_task_chat_dialogs(
            client,
            period,
            task_ids,
            max_pages=args.max_pages,
        )
        chats = merge_dialogs(chats, task_chat_dialogs)

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
    parser.add_argument("--chat-limit", type=int, default=200, help="Лимит диалогов")
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
