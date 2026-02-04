---
name: bitrix24-tasks
description: "Управление задачами Битрикс24. Активируется при упоминании: задачи битрикс, b24, bitrix24, битрикс24, задачи b24"
---

# Bitrix24 Tasks Skill

Skill для работы с задачами Битрикс24 через REST API.

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

## Статусы задач

| ID | Статус |
|----|--------|
| 2 | Ждёт выполнения |
| 3 | Выполняется |
| 4 | Ожидает контроля |
| 5 | Завершена |
| 6 | Отложена |

## Правило «мои задачи»

Вебхук привязан к конкретному пользователю. Его ID можно получить вызовом `profile.json`. **Если пользователь спрашивает про задачи без указания конкретного ответственного/постановщика**, всегда фильтруй по владельцу вебхука — добавляй оба фильтра через OR-логику:

1. Сначала получи ID текущего пользователя:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}profile.json"
```
Поле `result.ID` — это ID пользователя.

2. Затем делай **два запроса** (Битрикс24 не поддерживает OR в одном фильтре):
   - `filter[RESPONSIBLE_ID]=<USER_ID>` — где я ответственный
   - `filter[CREATED_BY]=<USER_ID>` — где я постановщик

3. Объедини результаты, убрав дубликаты по ID задачи.

**Если пользователь явно указал ответственного или постановщика** — используй только указанный фильтр.

## Правило удаления

**ОБЯЗАТЕЛЬНО**: перед вызовом `tasks.task.delete` запроси подтверждение у пользователя через `AskUserQuestion`. Все остальные операции выполняются без подтверждения.

---

## Активность по задачам

Когда пользователь спрашивает про действия/активность по задачам за период («что происходило с задачами», «какие действия были», «что нового по задачам»):

### Ограничения API

- Метод `tasks.task.history.list` **недоступен через вебхук** (Access denied).
- `CHANGED_DATE` **ненадёжен**: массовые обновления Битрикс (апдейты платформы) меняют `CHANGED_DATE` у тысяч старых задач.

### Важно: формат фильтров по датам

Фильтры по датам в `tasks.task.list` **требуют `--data-urlencode`** из-за символов `>`, `<`, `!` в именах параметров. Формат даты — `YYYY-MM-DD` (без времени и таймзоны).

Для фильтрации по конкретному дню используй граничные даты:
- `filter[>FIELD]=<день-до>` и `filter[<FIELD]=<день-после>`
- Пример для 2 февраля 2026: `filter[>CREATED_DATE]=2026-02-01` и `filter[<CREATED_DATE]=2026-02-03`

**Правильно:**
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.list.json" \
  --data-urlencode 'filter[>CREATED_DATE]=2026-02-01' \
  --data-urlencode 'filter[<CREATED_DATE]=2026-02-03' \
  -d 'filter[CREATED_BY]=1535' \
  -d 'select[]=ID' -d 'select[]=TITLE'
```

**Неправильно** (не работает — возвращает все задачи):
```bash
# НЕ ДЕЛАЙ ТАК:
-d 'filter[>=CREATED_DATE]=2026-02-02T00:00:00+05:00'
```

Аналогично для оператора «не равно»:
```bash
--data-urlencode 'filter[!CREATED_BY]=1535'   # правильно
-d 'filter[!=CREATED_BY]=1535'                 # неправильно
```

### Стратегия сбора активности

**Шаг 1: Задачи, созданные за период**

Два запроса (OR-логика):
```bash
# Где я постановщик — покажет задачи, которые я создал
source .env && curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.list.json" \
  -d 'filter[CREATED_BY]=<USER_ID>' \
  --data-urlencode 'filter[>CREATED_DATE]=<ДЕНЬ_ДО>' \
  --data-urlencode 'filter[<CREATED_DATE]=<ДЕНЬ_ПОСЛЕ>' \
  -d 'select[]=ID' -d 'select[]=TITLE' -d 'select[]=STATUS' \
  -d 'select[]=CREATED_DATE' -d 'select[]=RESPONSIBLE_ID'

# Где я ответственный, но создал кто-то другой — покажет задачи, которые мне поставили
source .env && curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.list.json" \
  -d 'filter[RESPONSIBLE_ID]=<USER_ID>' \
  --data-urlencode 'filter[>CREATED_DATE]=<ДЕНЬ_ДО>' \
  --data-urlencode 'filter[<CREATED_DATE]=<ДЕНЬ_ПОСЛЕ>' \
  --data-urlencode 'filter[!CREATED_BY]=<USER_ID>' \
  -d 'select[]=ID' -d 'select[]=TITLE' -d 'select[]=STATUS' \
  -d 'select[]=CREATED_DATE' -d 'select[]=CREATED_BY'
```

**Шаг 2: Задачи, закрытые за период**

```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.list.json" \
  -d 'filter[RESPONSIBLE_ID]=<USER_ID>' \
  -d 'filter[STATUS]=5' \
  --data-urlencode 'filter[>CLOSED_DATE]=<ДЕНЬ_ДО>' \
  --data-urlencode 'filter[<CLOSED_DATE]=<ДЕНЬ_ПОСЛЕ>' \
  -d 'select[]=ID' -d 'select[]=TITLE' -d 'select[]=CLOSED_DATE'
```

**Шаг 3: Новые сообщения в моих задачах**

Прямого способа получить «все сообщения за период по всем задачам» нет. Стратегия:

1. Получи список активных (незакрытых) задач с chatId:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.list.json" \
  -d 'filter[RESPONSIBLE_ID]=<USER_ID>' \
  --data-urlencode 'filter[!STATUS]=5' \
  -d 'order[ID]=desc' \
  -d 'select[]=ID' -d 'select[]=TITLE' -d 'select[]=CHAT_ID' -d 'start=0'
```

2. Для каждой задачи запроси последние сообщения чата (новая модель) или комментарии (legacy):

**Новая модель (если есть chatId)**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.dialog.messages.get.json" \
  -d 'DIALOG_ID=chat<CHAT_ID>' \
  -d 'LIMIT=20'
```
Фильтруй по `date`, исключай `author_id` = 0 (системные) и `author_id` = `<USER_ID>` (свои).

**Legacy (если chatId нет или пустой)**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}task.commentitem.getlist.json" \
  -d 'TASKID=<ID>' -d 'ORDER[ID]=desc'
```
Фильтруй по `POST_DATE`, исключай `AUTHOR_ID` = `"0"` (системные) и `AUTHOR_ID` = `<USER_ID>` (свои).

3. **Общие правила фильтрации**:
   - Оставь только сообщения, где дата попадает в запрошенный период
   - Исключи системные уведомления (автор = 0)
   - Исключи сообщения с типичным системным текстом: «просрочена», «Задача переведена в статус», «Крайний срок задачи изменён»

4. **Оптимизация**: не нужно опрашивать все задачи. Начни с 20–30 самых свежих активных задач. Если сообщений мало — расширь выборку.

### Формат вывода активности

Группируй по типу действия, не по задаче:

```
**Создал задачи:**
- #628902 «Не списывать праздничные дни отпусков» → на Замятина

**Мне поставили:**
- #629000 «Подготовить отчёт» → от Осташевой

**Закрыл:**
- #627050 «Сделать дашборд с открутками»

**Новые комментарии в моих задачах:**
- #626879 «Сделать файл рентабельности» — Осташева: «Проверь формулу в колонке D»
- #622102 «Заменить ставки в рентабельности» — Мамаева: «Готово, посмотри»
```

---

## API: tasks.task.list

Получить список задач с фильтрами, сортировкой и пагинацией.

**URL**: `${BITRIX24_WEBHOOK_URL}tasks.task.list.json`

**Параметры** (все опциональные):
- `filter[STATUS]` — фильтр по статусу (2-6)
- `filter[RESPONSIBLE_ID]` — фильтр по ответственному
- `filter[CREATED_BY]` — фильтр по постановщику
- `filter[>DEADLINE]` / `filter[<DEADLINE]` — фильтр по дедлайну (**через `--data-urlencode`**)
- `filter[>CREATED_DATE]` / `filter[<CREATED_DATE]` — фильтр по дате создания (**через `--data-urlencode`**, формат `YYYY-MM-DD`)
- `filter[>CLOSED_DATE]` / `filter[<CLOSED_DATE]` — фильтр по дате закрытия (**через `--data-urlencode`**, формат `YYYY-MM-DD`)
- `filter[!STATUS]` — исключить задачи с определённым статусом (**через `--data-urlencode`**)
- `filter[!CREATED_BY]` — исключить задачи с определённым постановщиком (**через `--data-urlencode`**)
- `filter[TITLE]` — фильтр по названию (частичное совпадение: `%текст%`)
- `order[DEADLINE]` — сортировка по дедлайну (`asc` / `desc`)
- `order[CREATED_DATE]` — сортировка по дате создания
- `order[ID]` — сортировка по ID
- `select[]` — выбор полей (ID, TITLE, STATUS, DEADLINE, RESPONSIBLE_ID, CREATED_BY, CREATED_DATE, CLOSED_DATE, PRIORITY и т.д.)

**Важно о фильтрах с операторами (`>`, `<`, `!`)**: передавай через `--data-urlencode`, а не через `-d`. Дату передавай в формате `YYYY-MM-DD` без времени. Подробнее — в секции «Активность по задачам».
- `start` — смещение для пагинации (0, 50, 100...)

**Шаблон**:
```bash
curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.list.json" \
  -d 'filter[STATUS]=3' \
  -d 'select[]=ID' \
  -d 'select[]=TITLE' \
  -d 'select[]=STATUS' \
  -d 'select[]=DEADLINE' \
  -d 'select[]=RESPONSIBLE_ID' \
  -d 'select[]=CREATED_BY' \
  -d 'select[]=GROUP_ID' \
  -d 'start=0'
```

**Ключевые поля ответа**:
```json
{
  "result": {
    "tasks": [
      {
        "id": "123",
        "title": "Название задачи",
        "status": "3",
        "deadline": "2025-01-15T18:00:00+03:00",
        "responsibleId": "1"
      }
    ]
  },
  "total": 42,
  "next": 50
}
```

---

## API: tasks.task.get

Получить детали задачи по ID.

**URL**: `${BITRIX24_WEBHOOK_URL}tasks.task.get.json`

**Параметры**:
- `taskId` — **обязательный**, ID задачи

**Шаблон**:
```bash
curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.get.json" \
  -d 'taskId=123'
```

**Ключевые поля ответа**:
```json
{
  "result": {
    "task": {
      "id": "123",
      "title": "Название",
      "description": "Описание задачи",
      "status": "3",
      "priority": "1",
      "deadline": "2025-01-15T18:00:00+03:00",
      "responsibleId": "1",
      "createdBy": "1",
      "createdDate": "2025-01-10T10:00:00+03:00",
      "tags": [],
      "group": {"id": "5", "name": "Проект"}
    }
  }
}
```

---

## API: tasks.task.add

Создать новую задачу.

**URL**: `${BITRIX24_WEBHOOK_URL}tasks.task.add.json`

**Параметры**:
- `fields[TITLE]` — **обязательный**, название задачи
- `fields[DESCRIPTION]` — описание
- `fields[RESPONSIBLE_ID]` — ID ответственного
- `fields[DEADLINE]` — дедлайн (формат: `2025-01-15T18:00:00+03:00`)
- `fields[PRIORITY]` — приоритет (0 = низкий, 1 = средний, 2 = высокий)
- `fields[GROUP_ID]` — ID проекта/группы
- `fields[TAGS][]` — теги
- `fields[CREATED_BY]` — постановщик (по умолчанию — владелец вебхука)

**Шаблон**:
```bash
curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.add.json" \
  -d 'fields[TITLE]=Новая задача' \
  -d 'fields[RESPONSIBLE_ID]=1' \
  -d 'fields[DEADLINE]=2025-01-20T18:00:00+03:00' \
  -d 'fields[PRIORITY]=1'
```

**Ответ**:
```json
{
  "result": {
    "task": {
      "id": "456"
    }
  }
}
```

---

## API: tasks.task.update

Обновить поля задачи, изменить статус или дедлайн.

**URL**: `${BITRIX24_WEBHOOK_URL}tasks.task.update.json`

**Параметры**:
- `taskId` — **обязательный**, ID задачи
- `fields[TITLE]` — новое название
- `fields[DESCRIPTION]` — новое описание
- `fields[STATUS]` — новый статус (2-6)
- `fields[DEADLINE]` — новый дедлайн
- `fields[RESPONSIBLE_ID]` — новый ответственный
- `fields[PRIORITY]` — новый приоритет

**Шаблон**:
```bash
curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.update.json" \
  -d 'taskId=123' \
  -d 'fields[STATUS]=5'
```

**Ответ**:
```json
{
  "result": {
    "task": true
  }
}
```

---

## API: tasks.task.delete

Удалить задачу. **ТРЕБУЕТСЯ подтверждение пользователя!**

**URL**: `${BITRIX24_WEBHOOK_URL}tasks.task.delete.json`

**Параметры**:
- `taskId` — **обязательный**, ID задачи

**Шаблон**:
```bash
curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.delete.json" \
  -d 'taskId=123'
```

**Ответ**:
```json
{
  "result": true
}
```

---

## Чат задачи (новая модель, tasks 25.700.0+)

С обновления `tasks 25.700.0` комментарии задач переехали в **чат задачи**. Чат — это стандартный IM-чат Битрикс24, привязанный к задаче. Вся переписка, системные события, файлы — всё в одном месте.

**Приоритет**: для новых задач используй чат. Старые методы `task.commentitem.*` оставлены для обратной совместимости и чтения старых комментариев.

### Получить chatId задачи

Через `tasks.task.get` с выбором поля `chat.id`:

```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.get.json" \
  -d 'taskId=123' \
  -d 'select[]=ID' -d 'select[]=TITLE' -d 'select[]=CHAT_ID'
```

Поле `chatId` в ответе — числовой ID чата. Для использования в IM-методах: `DIALOG_ID=chat<chatId>`.

### API: tasks.task.chat.message.send

Отправить сообщение в чат задачи.

**URL**: `${BITRIX24_WEBHOOK_URL}tasks.task.chat.message.send.json`

**Параметры**:
- `taskId` — **обязательный**, ID задачи
- `message` — **обязательный**, текст сообщения

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}tasks.task.chat.message.send.json" \
  -d 'taskId=123' \
  --data-urlencode 'message=Текст сообщения в чат задачи'
```

**Ответ**: ID отправленного сообщения.

### Чтение сообщений чата задачи

Используй стандартный IM-метод `im.dialog.messages.get` с `DIALOG_ID=chat<chatId>`:

```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.dialog.messages.get.json" \
  -d 'DIALOG_ID=chat<CHAT_ID>' \
  -d 'LIMIT=20'
```

Формат ответа — как в скилле `bitrix24-chats`: массив `messages` + массив `users`.

### Выбор метода: чат vs комментарии

| Ситуация | Метод |
|----------|-------|
| Написать в задачу | `tasks.task.chat.message.send` (предпочтительно) |
| Прочитать переписку задачи | `im.dialog.messages.get` с `DIALOG_ID=chat<chatId>` |
| Прочитать **старые** комментарии (до обновления) | `task.commentitem.getlist` |
| Написать комментарий (legacy) | `task.commentitem.add` |

---

## API: task.commentitem.getlist (legacy)

Получить список **старых комментариев** задачи. Для новых задач сообщения находятся в чате — используй `im.dialog.messages.get`.

**URL**: `${BITRIX24_WEBHOOK_URL}task.commentitem.getlist.json`

**Параметры**:
- `TASKID` — **обязательный**, ID задачи
- `ORDER[ID]` — сортировка (`asc` / `desc`)

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}task.commentitem.getlist.json" \
  -d 'TASKID=123' \
  -d 'ORDER[ID]=desc'
```

**Ключевые поля ответа**:
```json
{
  "result": [
    {
      "ID": "789",
      "AUTHOR_ID": "1",
      "POST_MESSAGE": "Текст комментария",
      "POST_DATE": "2025-01-12T14:30:00+03:00"
    }
  ]
}
```

---

## API: task.commentitem.add (legacy)

Добавить комментарий к задаче (старый метод). Для новых задач предпочтительнее `tasks.task.chat.message.send`.

**URL**: `${BITRIX24_WEBHOOK_URL}task.commentitem.add.json`

**Параметры**:
- `TASKID` — **обязательный**, ID задачи
- `FIELDS[POST_MESSAGE]` — **обязательный**, текст комментария

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}task.commentitem.add.json" \
  -d 'TASKID=123' \
  -d 'FIELDS[POST_MESSAGE]=Комментарий к задаче'
```

**Ответ**:
```json
{
  "result": "790"
}
```

---

## Формат вывода

При отображении результатов пользователю:

**Список задач** — таблица (всегда включай колонку «Проект»):
```
| ID  | Название           | Проект       | Статус       | Дедлайн    | Ответственный |
|-----|--------------------|--------------|--------------|------------|---------------|
| 123 | Сделать лендинг    | Клиент ABC   | Выполняется  | 15.01.2025 | Иванов И.     |
```

Название проекта берётся из поля `group.name` в ответе API. Если задача без проекта — ставь «—».

**Детали задачи** — структурированный блок:
```
Задача #123: Сделать лендинг
Проект: Клиент ABC
Статус: Выполняется
Приоритет: Средний
Дедлайн: 15.01.2025
Ответственный: ID 1
Постановщик: ID 1
Описание: ...
```

**Создание/обновление** — краткое подтверждение:
```
Задача #456 создана: "Новая задача"
```

Всегда преобразовывай числовые статусы в текстовые названия из таблицы статусов.

**Ссылки на задачи**: после каждого упоминания задачи добавляй голый URL на следующей строке с отступом (2 пробела). Домен берётся из `BITRIX24_WEBHOOK_URL` (часть до `/rest/`). Формат: `https://<домен>/workgroups/group/0/tasks/task/view/<ID>/`. Голый URL кликабелен в Terminal.app.
