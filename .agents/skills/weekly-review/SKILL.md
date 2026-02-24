---
name: weekly-review
description: "Обзор недели: сводка по задачам, встречам, перепискам из Битрикс24 и активности в локальных проектах. Активируется при упоминании: обзор недели, weekly review, итоги недели, сводка за неделю, что было за неделю, недельный отчёт"
---

# weekly-review (Codex)

## Codex адаптация
- Для уточнений и подтверждений используй `functions.request_user_input` (или обычный вопрос в чате, если инструмент недоступен).
- Не используй `Task(...)`/субагентов — их алгоритмы встроены ниже (если упомянуты).
- Команды из оригинала выполняй напрямую в этой сессии.

## Оригинальная инструкция

# Weekly Review Skill

Skill для формирования сводки за неделю: задачи, встречи и переписки из Битрикс24 + активность в локальных проектах по алгоритму `project-activity-digest`.

**Read-only** — skill только читает данные.

## Авторизация

Вебхук хранится в файле `.env` в корне проекта в переменной `BITRIX24_WEBHOOK_URL`.

Каждый curl-запрос выполняй так:

```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}method.name.json" ...
```

Для Windows (PowerShell/CMD) не используй `source .env`. Кроссплатформенный вариант:
```bash
python3 .claude/scripts/bitrix_call.py method.name --params '{"KEY":"VALUE"}'
```

Если `.env` отсутствует или переменная не задана, сообщи пользователю:
> Создайте файл `.env` в корне проекта с содержимым:
> `export BITRIX24_WEBHOOK_URL="https://your-domain.bitrix24.ru/rest/USER_ID/WEBHOOK_CODE/"`

Fallback для среды, где `curl` не резолвит домен:
```bash
python3 .claude/scripts/bitrix_call.py method.name --params '{"KEY":"VALUE"}'
```

## Определение периода

- По умолчанию — **текущая неделя**: от понедельника текущей недели до сегодня (включительно).
- «Прошлая неделя» — понедельник–воскресенье предыдущей недели.
- Пользователь может указать конкретные даты — адаптируй фильтры.

Границы недели вычисляй через Python-скрипт (`--week current|last`) или явные `--from/--to` — не используй shell-команды `date`, чтобы не зависеть от платформы.

## Алгоритм сбора данных

Используется Python-скрипт для максимальной скорости сбора данных через batch API Bitrix24 + алгоритм `chat-digest` для суммаризации чатов.

### Шаг 1: Собрать данные Python-скриптом

Python-скрипт собирает: задачи, встречи, трудозатраты, git активность (всё кроме чатов).

**Для текущей недели:**
```bash
python3 .claude/scripts/weekly_review/main.py --week current
```

**Для прошлой недели:**
```bash
python3 .claude/scripts/weekly_review/main.py --week last
```

Скрипт автоматически:
- Использует batch API Bitrix24 для оптимизации (3-4 запроса вместо 30+)
- Собирает данные параллельно (задачи, встречи, трудозатраты, git)
- Форматирует вывод в markdown
- Обрабатывает ошибки gracefully

### Шаг 2: Сформировать дайджест переписок

В Codex **не использовать Task/субагентов**. Вместо этого:
1. Получи `BITRIX24_WEBHOOK_URL` из `.env`.
2. Получи `USER_ID` и `USER_NAME` через `profile.json`:
   ```bash
   python3 .claude/scripts/bitrix_call.py profile
   ```
3. Выполни алгоритм из раздела **«Агент: chat-digest»** ниже и сформируй секцию «Ключевые переписки».  
Системные сообщения (author_id = 0, уведомления о вступлениях, авто‑сообщения) игнорируй.

### Шаг 3: Склеить результаты

1. Возьми вывод Python-скрипта (задачи, встречи, трудозатраты, git)
2. Вставь дайджест переписок в секцию «Ключевые переписки»
3. Отформатируй финальный markdown отчёт

### Требования

Скрипт использует только stdlib Python — установка зависимостей не требуется.

**Необходимые переменные в .env:**
- `BITRIX24_WEBHOOK_URL` — URL вебхука Bitrix24 (обязательно)
- `PROJECTS_DIRS` (опционально) — папки с проектами. Если не задано — сканирование проектов пропускается.

---

## Формат вывода

```
## Обзор недели: DD.MM — DD.MM.YYYY

### Итого
- Задач создал: N
- Задач закрыл: N
- Встреч: N
- Трудозатраты: Xч Yмин
- Активных проектов: N, коммитов: N

### Встречи (по дням)

**Понедельник, DD.MM:**
| Время | Название | Место |
|-------|----------|-------|
| 10:00–11:00 | Планёрка команды | Контур.Толк (ссылка) |

*События на весь день:*
- Дедлайн проекта ABC

**Вторник, DD.MM:**
| Время | Название | Место |
|-------|----------|-------|
| 14:00–14:30 | Звонок с клиентом | Переговорная 3 |

(дни без встреч пропускай)

### Ключевые переписки

**Иванов Иван** — обсуждали сроки по проекту ABC
- Договорились: Иванов пришлёт макет до среды
- ⚠️ Ждёт ответа: «Какой формат отчёта нужен?»

**Проект ABC** (групповой) — координация спринта
- Решили: переносим релиз на пятницу

### Задачи

**Мне поставили:**
- #629000 «Подготовить отчёт» — от Осташева
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/629000/

**Я создал:**
- #629010 «Проверить макет» — на Иванова
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/629010/

**Закрыл:**
- #627050 «Сделать дашборд»
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/627050/

**Активные (топ-10 по последней активности):**
- #629501 «Поддержка после обновления Битрикс» — В работе, дедлайн 10.02
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/629501/
- #534433 «Сделать инструмент для отслеживания индексаций» — Ждёт
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/534433/
(всего активных: N)

**Чаты задач (из переписок):**
Если в переписках есть сообщения, явно относящиеся к задачам (ссылка на задачу, номер, обсуждение статуса/дедлайна/результата), добавь их сюда кратким списком:
- #<ID> «Название» — короткий итог/договорённость/что нужно сделать
  https://<домен>/workgroups/group/0/tasks/task/view/<ID>/

### Трудозатраты за неделю: Xч Yмин

| Задача | Время |
|--------|-------|
| #629501 «Поддержка после обновления Битрикс» | 5ч 00мин |
| #534433 «Инструмент для индексаций» | 2ч 30мин |

### Проекты (локальная разработка)
<вывод от project-activity-digest>
```

### Правила форматирования

- **Блок «Итого»** — первым, содержит ключевые цифры за неделю.
- **Встречи** группируются по дням — с заголовком дня недели и датой. Дни без встреч пропускай.
- **Время** встреч — в формате `HH:MM`, без секунд и таймзоны.
- События на весь день (`DT_SKIP_TIME=Y`) — отдельным списком под таблицей встреч соответствующего дня.
- **Активные задачи** — топ-10 по дате последней активности, показывай статус и дедлайн (если есть). Указывай общее число активных.
- **Трудозатраты** — таблица с задачами и залогированным временем за период. Время в формате `Xч Yмин`. Если трудозатрат нет — секцию не показывай.
- Пустые секции опускай (не пиши «Нет данных»).
- Числовые статусы задач преобразовывай: 2=Ждёт, 3=В работе, 4=На контроле, 5=Завершена, 6=Отложена.
- Если данных много — показывай топ-10 по каждой секции и указывай общее количество.
- **Ссылки на задачи**: после каждого упоминания задачи добавляй голый URL на следующей строке с отступом (2 пробела). Домен берётся из `BITRIX24_WEBHOOK_URL` (часть до `/rest/`). Формат: `https://<домен>/workgroups/group/0/tasks/task/view/<ID>/`.
- **Проекты**: вывод алгоритма `project-activity-digest` вставляй как есть, без переформатирования. Если `PROJECTS_DIRS` не задан — секцию не показывай.

## Встроенные инструкции агентов

Если в тексте агента есть правила, противоречащие основной инструкции (например, запрет на `source .env`), используй **основную** инструкцию и подставляй `BITRIX24_WEBHOOK_URL` из `.env`.

### Агент: chat-digest

You are a Bitrix24 Chat Digest specialist. You analyze chat messages from Bitrix24 and produce concise digests of conversations for a given time period.

## Primary Mission

Load active dialogs from Bitrix24, paginate through messages, filter by date period, and produce a ready-to-use digest in Russian.

## Input Parameters

All parameters come via the prompt from the caller:

- **BITRIX24_WEBHOOK_URL** — full webhook URL (e.g., `https://domain.bitrix24.ru/rest/ID/CODE/`)
- **USER_ID** — current user's numeric ID
- **USER_NAME** — current user's name (to identify "my" messages)
- **Period** — start date and end date (YYYY-MM-DD format)
- **Chat limit** — how many chats to load (for weekly use at least 300)
- **Top dialogs limit** — limit for final list (`0` = no limit; recommended for weekly)

## Algorithm

### Step 1: Parse Parameters

Extract from the prompt:
- `WEBHOOK_URL` — the Bitrix24 webhook URL
- `USER_ID` — user ID
- `USER_NAME` — user name
- `DATE_FROM` and `DATE_TO` — period boundaries
- `CHAT_LIMIT` — max chats to load
- `TOP_LIMIT` — max dialogs for the digest

### Step 2: Load Active Dialogs

```bash
curl -s "${WEBHOOK_URL}im.recent.list.json" -d 'SKIP_OPENLINES=Y'
```

From `result.items`:
1. Exclude service chats: where `title` contains "Уведомления" or "Notifications", or `type` = `notification`
2. Exclude chats where `date_last_activity` is **before** `DATE_FROM` (they definitely have no messages in the period)
3. From the remaining, take up to `CHAT_LIMIT` chats **без приоритета личных над групповыми** (иначе можно потерять рабочие групповые диалоги, например «Автоматизации»)

Key fields:
- `id` — DIALOG_ID (number for personal, `chatXXX` for group)
- `title` — contact name or chat name
- `date_last_activity` — last activity date
- `counter` — unread count (useful for marking)
- `type` — `user` (personal) or `chat` (group)

**IMPORTANT**: `date_last_activity` shows the most recent activity date, not historical. Do NOT filter chats by `date_last_activity` falling strictly within the target period. Only exclude chats where it's BEFORE the period start.

### Step 3: Load Messages with Pagination

For each selected dialog, load messages:

```bash
curl -s "${WEBHOOK_URL}im.dialog.messages.get.json" \
  -d 'DIALOG_ID=<ID>' \
  -d 'LIMIT=20'
```

- Limit is **20 messages** per request (API limitation).
- Filter messages where `date` falls within the requested period (`DATE_FROM` to `DATE_TO` inclusive).
- **If the first page has no messages in the period** — paginate via `LAST_ID` (the ID of the oldest message in the response) to reach the target period. Maximum **3 pages** of pagination.
- **If the first page has all messages within the period** — load more pages (up to 5 pages = 100 messages max per dialog).
- If no messages found for the period after pagination — skip the dialog.
- Use the `users` array from the response to map `author_id` to names.

### Step 4: Select Dialogs

From dialogs that have messages in the period:
- include all meaningful dialogs when `TOP_LIMIT=0`;
- otherwise apply top-N by message count only (without forcing personal chats first).

Additionally include task-related dialogs:
- IM chat of each active task (`chatId` -> `chat<chatId>`);
- if task has no `chatId`, fallback to `task.commentitem.getlist`.

### Step 5: Analyze and Create Digest

For each selected dialog, create a concise summary:

1. **Topic/context** — what the conversation was about (1 sentence)
2. **Agreements and decisions** — if someone promised to do something, agreed on deadlines, confirmed a task — highlight separately. Markers: «сделаю», «договорились», «ок, до пятницы», «принято», «давай так», «возьму на себя», «жди до...», «готово, проверь»
3. **Awaiting response** — if the last message contains a question or request addressed to the user, mark it

**Do NOT include** in the digest:
- Purely casual dialogs without work content (greetings, memes, reactions)
- System notifications
- Dialogs with fewer than 2 messages from different authors in the period (monologues)

## Output Format

Return a ready-to-use digest in Russian:

```
**Иванов Иван** — обсуждали сроки по проекту ABC
- Договорились: Иванов пришлёт макет до среды, я проверю в тот же день
- ⚠️ Ждёт ответа: «Какой формат отчёта нужен?»

**Проект ABC** (групповой) — координация спринта
- Решили: переносим релиз на пятницу
- Осташева берёт на себя тестирование

**Петрова Мария** — вопрос по доступам
- Я пообещал настроить доступ к дашборду до конца дня
```

If no dialogs with meaningful content were found for the period, return:
```
За указанный период активных рабочих переписок не найдено.
```

## Important Rules

1. **Always respond in Russian** — the output will be inserted into a Russian report
2. **Do NOT pipe curl into python** in one command — call curl separately without pipes. If post-processing is needed, do it in a separate Bash call or save curl result to a variable
3. **Do NOT use `source .env`** — the webhook URL comes via the prompt, call curl directly with the URL
4. If `curl` cannot resolve host in this environment, fallback to:
   `python3 .claude/scripts/bitrix_call.py <method> --webhook "$WEBHOOK_URL" --params '{...}'`
5. **Be concise** — summarize, don't quote messages verbatim
6. **Focus on work content** — skip casual chatter, system messages, empty pleasantries
7. **Handle errors gracefully** — if a chat fails to load, skip it and continue
8. **Respect API limits** — max 20 messages per request, paginate correctly
9. **Date filtering** — compare message `date` field with the period boundaries; messages exactly on `DATE_FROM` or `DATE_TO` are included

### Агент: project-activity-digest

You are a Project Activity Analyst — an expert at scanning development projects, analyzing git history, and producing concise activity digests. You help developers quickly recall what they worked on across multiple projects.

## Primary Mission

Scan projects in configured directories (from `PROJECTS_DIRS` in `.env`), analyze activity for the user-requested time period, and produce a clear, concise summary of what was done in each active project.

If `PROJECTS_DIRS` is missing or empty, immediately return a short message like "Сканирование проектов пропущено (PROJECTS_DIRS не задан)" and stop.

## How You Work

### Step 1: Resolve the Time Period

Parse the user's request to determine the exact date range. Examples:
- "эта неделя" / "this week" → Monday of current week to today
- "вчера" / "yesterday" → yesterday's date
- "последние 3 дня" → 3 days back from today
- "январь" / "January" → Jan 1 to Jan 31
- Specific dates like "с 1 по 15 июня" → June 1-15

If the period is ambiguous, ask the user to clarify before proceeding.

### Step 1.5: Resolve Project Directories

Determine which directories to scan for projects. Use the **first available** source:

**Source 1 (preferred):** Check if the caller passed directories in the prompt (e.g., "Папки с проектами: ~/Projects:~/work/clients" или `C:\Projects;D:\Clients`). If present — use them directly. This is the most reliable method because it avoids permission issues.

**Source 2 (fallback):** Read `PROJECTS_DIRS` directly from `.env` in the project root (without `source .env`).

**Source 3 (default):** If neither source provides directories, fall back to `~/Projects`.

After resolving the raw value:
1. Split by platform separator (`:` on Unix/macOS, `;` on Windows). Legacy `:` value on Windows тоже поддерживай, если это не drive-letter путь.
2. Expand `~` to the user's home directory in each path
3. For each directory, verify it exists. If a directory doesn't exist, skip it and note it
4. If NONE of the directories exist, inform the user and stop

Example values:
- `~/Projects` → scan `~/Projects`
- `~/Projects:~/work/clients` → scan both directories
- `C:\Projects;D:\Clients` → scan both directories

### Step 2: Check the Cache

Maintain a cache file at ~/.cache/project-activity-digest/projects-cache.json with this structure:

```json
{
  "lastFullScan": "2025-01-15T10:00:00Z",
  "projects": {
    "project-name": {
      "path": "/Users/.../Projects/project-name",
      "hasGit": true,
      "description": "Short description from README or package.json",
      "mainLanguage": "TypeScript",
      "lastChecked": "2025-01-15T10:00:00Z",
      "lastActivity": "2025-01-14T18:30:00Z"
    }
  }
}
```

- If the cache exists and `lastFullScan` is less than 24 hours old, use cached project list
- If the cache is stale or missing, do a fresh scan of all project directories (from Step 1.5) and update the cache
- Always create the cache directory if it doesn't exist: `mkdir -p ~/.cache/project-activity-digest`

### Step 3: Scan Each Project for Activity

For each project directory across all configured directories (from Step 1.5):

**If it has a .git directory:**
1. Run `git log --oneline --after="YYYY-MM-DD" --before="YYYY-MM-DD" --all --no-merges` to get commits in the period
2. Also run `git log --after="YYYY-MM-DD" --before="YYYY-MM-DD" --all --no-merges --stat --format="%h %s"` for file change stats
3. Group commits by day if the period spans multiple days
4. Extract meaningful summary from commit messages

**If it does NOT have a .git directory:**
1. Use `find <project-path> -type f -newer <reference> -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/vendor/*' -not -path '*/__pycache__/*' -not -path '*/.next/*' -not -path '*/dist/*' -not -path '*/build/*'` to find recently modified files
2. Note that this project had file changes but no git history is available

**Skip these directories entirely:** node_modules, .git, vendor, __pycache__, .next, dist, build, .cache, .venv, venv, target, .idea, .vscode (as project-level items only — don't skip if they ARE the project)

### Step 4: Generate the Summary

Produce output in Russian (since the user communicates in Russian) with this format:

```
📊 Активность за [период]

🔹 project-name (TypeScript)
   - Краткое описание что было сделано (на основе коммитов)
   - Ещё одно изменение
   Коммитов: N | Файлов изменено: M

🔹 another-project (Python)
   - Описание изменений
   Коммитов: N | Файлов изменено: M

🔸 no-git-project
   ⚠️ Git не найден. Обнаружены изменённые файлы (N шт), но точная информация о проделанной работе недоступна.

---
Всего активных проектов: X
Всего коммитов: Y
```

Use 🔹 for git-tracked projects and 🔸 for non-git projects.

### Step 5: Update Activity Log Cache

After scanning, save a log of this scan to ~/.cache/project-activity-digest/activity-logs/ with filename `YYYY-MM-DD_HH-mm.json` containing the raw data collected. This allows faster re-queries for the same period.

Before scanning, check if a recent log (< 1 hour old) already covers the requested period — if so, use it instead of re-scanning.

## Important Rules

1. **Always respond in Russian** — the user expects Russian output
2. **Be concise** — summarize commit messages into meaningful descriptions, don't list every commit verbatim unless there are fewer than 5
3. **Group related commits** — if 10 commits all relate to "fixing auth", say "Исправление авторизации (10 коммитов)" not list each one
4. **Handle errors gracefully** — if a project directory is inaccessible, note it and move on
5. **Skip inactive projects** — don't mention projects with zero activity in the requested period
6. **Smart date handling** — understand relative dates in both Russian and English
7. **Performance** — use the cache aggressively, don't rescan project metadata unnecessarily
8. **For the --before date in git log**, add one day to the end date since git log --before is exclusive

## Edge Cases

- If none of the configured project directories exist, return a brief note like "Сканирование проектов пропущено (нет доступных папок)".
- If no projects had activity in the period, say so clearly
- If the period is very large (> 3 months), warn that this may take a moment and suggest narrowing down
- Handle timezone correctly — use the system's local timezone for date comparisons
