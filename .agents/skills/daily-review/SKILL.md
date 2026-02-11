---
name: daily-review
description: "Обзор дня: сводка по чатам, задачам, встречам из Битрикс24 и активности в локальных проектах. Активируется при упоминании: обзор дня, дайджест, сводка дня, что нового, что произошло за день, daily review"
---

# daily-review (Codex)

## Codex адаптация
- Вместо `AskUserQuestion` используй `functions.request_user_input`.
- Не используй `Task(...)`/субагентов — их алгоритмы встроены ниже (если упомянуты).
- Команды из оригинала выполняй напрямую в этой сессии.

## Оригинальная инструкция

# Daily Review Skill

Skill для формирования сводки рабочего дня из Битрикс24: непрочитанные чаты, активность по задачам, встречи из календаря.

**Read-only** — skill только читает данные.

## Авторизация

Вебхук хранится в файле `.env` в корне проекта в переменной `BITRIX24_WEBHOOK_URL`.

Каждый curl-запрос выполняй так:

```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}method.name.json" ...
```

Если `.env` отсутствует или переменная не задана, сообщи пользователю:
> Создайте файл `.env` в корне проекта с содержимым:
> `export BITRIX24_WEBHOOK_URL="https://your-domain.bitrix24.ru/rest/USER_ID/WEBHOOK_CODE/"`

### ВАЖНО: не пайпить curl в python/jq в одной команде

**НИКОГДА** не делай `source .env && curl ... | python3 ...` — `source` может сломать пайп, и python получит пустой stdin.

Правильный подход — вызывать curl **отдельной командой** без пайпа. Если нужна постобработка — делай в два отдельных вызова Bash, либо сохраняй результат curl в переменную:

```bash
# НЕПРАВИЛЬНО (ломается):
source .env && curl -s "${BITRIX24_WEBHOOK_URL}method.json" | python3 -c "..."

# ПРАВИЛЬНО — curl без пайпа:
source .env && curl -s "${BITRIX24_WEBHOOK_URL}method.json"
```

## Определение периода

- По умолчанию — **сегодня** (текущая дата).
- Пользователь может попросить обзор за вчера, за неделю, за конкретную дату — адаптируй фильтры.
- Дата берётся из текущего контекста (сегодня задаётся системой).

## Алгоритм сбора данных (оптимизированный)

Все данные собираются через единый Python‑скрипт с batch запросами, параллельными вызовами и кешем чатов.

### Шаг 0: Определить период

- По умолчанию — **вчера** (относительно текущей даты).
- Можно указать конкретную дату или диапазон.

### Шаг 1: Запустить быстрый сбор

**За вчера:**
```bash
python3 .claude/scripts/daily_review/main.py --yesterday
```

**За конкретную дату:**
```bash
python3 .claude/scripts/daily_review/main.py --date 2026-02-10
```

**За диапазон:**
```bash
python3 .claude/scripts/daily_review/main.py --from 2026-02-01 --to 2026-02-07
```

Скрипт вернёт JSON со всеми данными:
- Профиль пользователя
- Задачи (созданные, поставленные, закрытые, дедлайны)
- Встречи календаря
- Чаты (с кешем на 24 часа)
- Git‑активность по проектам

### Кеш чатов

Кеш хранится в `~/.cache/daily-review/chat-digest/`.  
Если нужно принудительно обновить чаты — удали соответствующий файл кеша.

### Шаг 2: Сформировать отчёт

Проанализируй JSON и собери отчёт по формату ниже.

**Правила:**
- Встречи показывай только со статусом участия `Y` или `Q`.
- Если чатов нет — секцию «Переписки» пропускай.
- Если git‑активности нет — секцию «Проекты» пропускай.

Где:
- `<ДАТА_ОТ>` и `<ДАТА_ДО>` — границы запрашиваемого дня (например, `2026-02-04` и `2026-02-04`)
- `<ЗНАЧЕНИЕ_PROJECTS_DIRS>` — значение переменной, прочитанное из `.env` (например, `~/Projects` или `~/Projects:~/work/clients`). Может быть пустым — тогда секцию «Проекты» пропусти.

Для секции «Переписки» используй алгоритм из раздела **«Агент: chat-digest»** ниже, но работай по данным `chats` из JSON (без дополнительных API вызовов, если данные уже есть).  
Для ежедневного обзора включай **все рабочие диалоги** за день (не только топ).
Системные сообщения (author_id = 0, уведомления о вступлениях, авто‑сообщения) игнорируй.

Результат project-activity-digest включи в итоговую сводку в секцию «Проекты». Если `PROJECTS_DIRS` не задан или за день коммитов не было — секцию не показывай.

---

## Формат вывода

Выводи результат в виде структурированной сводки. Адаптируй секции под наличие данных — пустые секции не показывай.

```
## Обзор дня: <дата>

### Встречи
| Время | Название | Место |
|-------|----------|-------|
| 10:00–11:00 | Планёрка команды | Контур.Толк (ссылка) |
| 14:00–14:30 | Звонок с клиентом | Переговорная 3 |

*Событий на весь день:*
- Дедлайн проекта ABC

### Переписки

**Иванов Иван** — обсуждали сроки по проекту ABC
- Договорились: Иванов пришлёт макет до среды, я проверю в тот же день
- ⚠️ Ждёт ответа: «Какой формат отчёта нужен?»

**Проект ABC** (групповой) — координация спринта
- Решили: переносим релиз на пятницу
- Осташева берёт на себя тестирование

**Петрова Мария** — вопрос по доступам
- Я пообещал настроить доступ к дашборду до конца дня

### Задачи

**Горящие дедлайны (сегодня):**
- #628902 «Подготовить презентацию» — дедлайн 18:00
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/628902/

**Мне поставили:**
- #629000 «Подготовить отчёт» — от Осташева
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/629000/

**Я создал:**
- #629010 «Проверить макет» — на Иванова
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/629010/

**Закрыл:**
- #627050 «Сделать дашборд»
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/627050/

**Новые комментарии:**
- #626879 «Файл рентабельности» — Осташева: «Проверь формулу в колонке D»
  https://team.up-advert.ru/workgroups/group/0/tasks/task/view/626879/

**Чаты задач (из переписок):**
Если в переписках есть сообщения, явно относящиеся к задачам, добавь их сюда кратким списком.  
Считать задачей любое из:
- ссылка на задачу (URL `/tasks/task/view/<ID>/`)
- вложение/карточка задачи в сообщении (ATTACH/GRID с ссылкой или названием задачи)
- явное упоминание ID/названия задачи при обсуждении статуса/дедлайна/результата

- Если в чате задачи идёт обсуждение, обязательно добавь сюда, даже если задача не в списках created/assigned/closed/deadlines.
- #<ID> «Название» — короткий итог/договорённость/что нужно сделать
  https://<домен>/workgroups/group/0/tasks/task/view/<ID>/

### Проекты (локальная разработка)
<вывод от project-activity-digest>
```

### Правила форматирования

- **Встречи** идут первыми — это самое срочное (можно опоздать).
- **Время** встреч — в формате `HH:MM`, без секунд и таймзоны.
- События на весь день (`DT_SKIP_TIME=Y`) — отдельным списком под таблицей встреч.
- **Горящие дедлайны** — перед остальными задачами, выделяются как важные.
- Пустые секции опускай (не пиши «Нет данных»).
- Числовые статусы задач преобразовывай: 2=Ждёт, 3=В работе, 4=На контроле, 5=Завершена, 6=Отложена.
- Если данных много — показывай топ-10 по каждой секции и указывай общее количество.
- **Ссылки на задачи**: после каждого упоминания задачи добавляй голый URL на следующей строке с отступом (2 пробела). Домен берётся из `BITRIX24_WEBHOOK_URL` (часть до `/rest/`). Формат: `https://<домен>/workgroups/group/0/tasks/task/view/<ID>/`. Голый URL кликабелен в Terminal.app.
- **Проекты**: вывод алгоритма `project-activity-digest` вставляй как есть, без переформатирования. Если `PROJECTS_DIRS` не задан — секцию не показывай. Если за день коммитов не было — секцию не показывай.

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
- **Chat limit** — how many chats to load (e.g., 20 for daily, 15 for weekly)
- **Top dialogs limit** — how many top dialogs to include in the digest (e.g., 15 for daily, 10 for weekly)

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
3. From the remaining, take up to `CHAT_LIMIT` chats (priority: personal `user` > group `chat`)

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

### Step 4: Select Top Dialogs

From dialogs that have messages in the period, select **top N** (by `TOP_LIMIT`) by message count. Priority: personal (`user`) first, then group (`chat`).

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
4. **Be concise** — summarize, don't quote messages verbatim
5. **Focus on work content** — skip casual chatter, system messages, empty pleasantries
6. **Handle errors gracefully** — if a chat fails to load, skip it and continue
7. **Respect API limits** — max 20 messages per request, paginate correctly
8. **Date filtering** — compare message `date` field with the period boundaries; messages exactly on `DATE_FROM` or `DATE_TO` are included

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

**Source 1 (preferred):** Check if the caller passed directories in the prompt (e.g., "Папки с проектами: ~/Projects:~/work/clients"). If present — use them directly. This is the most reliable method because it avoids permission issues.

**Source 2 (fallback):** Read `PROJECTS_DIRS` from `.env` in the project root:
```bash
source .env 2>/dev/null && echo "$PROJECTS_DIRS"
```

**Source 3 (default):** If neither source provides directories, fall back to `~/Projects`.

After resolving the raw value:
1. Split by `:` to get a list of directories
2. Expand `~` to the user's home directory in each path
3. For each directory, verify it exists. If a directory doesn't exist, skip it and note it
4. If NONE of the directories exist, inform the user and stop

Example values:
- `~/Projects` → scan `~/Projects`
- `~/Projects:~/work/clients` → scan both directories

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
