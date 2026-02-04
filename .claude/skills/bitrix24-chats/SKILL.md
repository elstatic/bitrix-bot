---
name: bitrix24-chats
description: "Чтение чатов и переписок Битрикс24. Активируется при упоминании: чаты битрикс, переписка b24, сообщения битрикс, мессенджер битрикс24, диалоги b24, чаты b24"
---

# Bitrix24 Chats Skill

Skill для чтения чатов и сообщений Битрикс24 через REST API (im.*).

**Все методы read-only** — skill только читает данные мессенджера.

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

## Ключевые особенности

### DIALOG_ID

- **Личный диалог**: DIALOG_ID = ID пользователя (число), например `42`
- **Групповой чат**: DIALOG_ID = `chatXXX`, например `chat153`

### Пагинация

- **`im.recent.list`**: через параметр `LAST_MESSAGE_DATE` — берётся из поля `DATE_MESSAGE` последнего элемента предыдущей страницы
- **`im.dialog.messages.get`**: через `LAST_ID` (старые сообщения) / `FIRST_ID` (новые сообщения), лимит **20 сообщений** за запрос

### Поиск по содержимому сообщений

**API не поддерживает полнотекстовый поиск по сообщениям.** Если пользователь просит найти сообщение по тексту:
1. Загрузи сообщения диалога постранично через `im.dialog.messages.get`
2. Фильтруй на своей стороне по нужному тексту
3. Для экономии запросов сначала уточни у пользователя примерный период или диалог

### Контекст владельца вебхука

API автоматически возвращает чаты и сообщения от имени владельца вебхука. «Мои чаты» = чаты этого пользователя.

---

## API: im.recent.list

Список недавних диалогов с последним сообщением.

**URL**: `${BITRIX24_WEBHOOK_URL}im.recent.list.json`

**Параметры** (все опциональные):
- `LAST_MESSAGE_DATE` — дата последнего сообщения для пагинации (формат из ответа API)
- `ONLY_OPENLINES` — `Y` для чатов открытых линий
- `SKIP_OPENLINES` — `Y` чтобы исключить открытые линии
- `SKIP_CHAT` — `Y` чтобы исключить групповые чаты
- `SKIP_DIALOG` — `Y` чтобы исключить личные диалоги

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.recent.list.json" \
  -d 'SKIP_OPENLINES=Y'
```

**Ключевые поля ответа**:
```json
{
  "result": {
    "items": [
      {
        "id": "42",
        "type": "user",
        "avatar": {},
        "title": "Иванов Иван",
        "message": {
          "id": 12345,
          "text": "Текст последнего сообщения",
          "date": "2025-01-15T14:30:00+03:00",
          "author_id": 42
        },
        "counter": 3,
        "date_message": "2025-01-15T14:30:00+03:00"
      },
      {
        "id": "chat153",
        "type": "chat",
        "title": "Проект ABC",
        "message": {
          "id": 12350,
          "text": "Последнее сообщение в чате",
          "date": "2025-01-15T15:00:00+03:00",
          "author_id": 7
        },
        "counter": 0,
        "date_message": "2025-01-15T15:00:00+03:00"
      }
    ]
  }
}
```

**Пагинация**: для следующей страницы передай `LAST_MESSAGE_DATE` = значение `date_message` из последнего элемента.

---

## API: im.recent.get

Сокращённый список недавних чатов (без полных данных сообщений).

**URL**: `${BITRIX24_WEBHOOK_URL}im.recent.get.json`

**Параметры** (все опциональные):
- `ONLY_OPENLINES` — `Y` для открытых линий
- `SKIP_OPENLINES` — `Y` исключить открытые линии

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.recent.get.json" \
  -d 'SKIP_OPENLINES=Y'
```

**Ключевые поля ответа**: аналогично `im.recent.list`, но с сокращённым набором данных.

---

## API: im.dialog.messages.get

Получить сообщения конкретного диалога.

**URL**: `${BITRIX24_WEBHOOK_URL}im.dialog.messages.get.json`

**Параметры**:
- `DIALOG_ID` — **обязательный**, ID диалога (число для личного, `chatXXX` для группового)
- `LIMIT` — количество сообщений (макс. **20**)
- `LAST_ID` — ID сообщения для пагинации назад (загрузить старее этого)
- `FIRST_ID` — ID сообщения для пагинации вперёд (загрузить новее этого)

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.dialog.messages.get.json" \
  -d 'DIALOG_ID=42' \
  -d 'LIMIT=20'
```

**Для пагинации (загрузка старых сообщений)**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.dialog.messages.get.json" \
  -d 'DIALOG_ID=42' \
  -d 'LAST_ID=12300' \
  -d 'LIMIT=20'
```

**Ключевые поля ответа**:
```json
{
  "result": {
    "messages": [
      {
        "id": 12345,
        "chat_id": 100,
        "author_id": 42,
        "date": "2025-01-15T14:30:00+03:00",
        "text": "Текст сообщения",
        "params": {}
      }
    ],
    "users": [
      {
        "id": 42,
        "name": "Иванов Иван",
        "first_name": "Иван",
        "last_name": "Иванов"
      }
    ],
    "chat_id": 100
  }
}
```

**Важно**: ответ содержит массив `users` с данными авторов — используй его для отображения имён вместо ID.

---

## API: im.dialog.get

Получить данные о диалоге (метаинформация).

**URL**: `${BITRIX24_WEBHOOK_URL}im.dialog.get.json`

**Параметры**:
- `DIALOG_ID` — **обязательный**, ID диалога

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.dialog.get.json" \
  -d 'DIALOG_ID=42'
```

**Ключевые поля ответа**:
```json
{
  "result": {
    "id": 100,
    "type": "private",
    "name": "Иванов Иван",
    "owner": 42,
    "date_create": "2025-01-10T10:00:00+03:00",
    "message_count": 150
  }
}
```

---

## API: im.search.user.list

Поиск пользователя по имени (для определения DIALOG_ID).

**URL**: `${BITRIX24_WEBHOOK_URL}im.search.user.list.json`

**Параметры**:
- `FIND` — **обязательный**, строка поиска (имя или фамилия)

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.search.user.list.json" \
  -d 'FIND=Иванов'
```

**Ключевые поля ответа**:
```json
{
  "result": [
    {
      "id": 42,
      "name": "Иванов Иван",
      "first_name": "Иван",
      "last_name": "Иванов",
      "work_position": "Менеджер",
      "department": "Отдел продаж"
    }
  ]
}
```

**Использование**: найденный `id` пользователя = его `DIALOG_ID` для личного диалога.

---

## API: im.search.chat.list

Поиск группового чата по названию.

**URL**: `${BITRIX24_WEBHOOK_URL}im.search.chat.list.json`

**Параметры**:
- `FIND` — **обязательный**, строка поиска (название чата)

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.search.chat.list.json" \
  -d 'FIND=Проект'
```

**Ключевые поля ответа**:
```json
{
  "result": [
    {
      "id": 153,
      "name": "Проект ABC",
      "owner": 1,
      "date_create": "2025-01-05T09:00:00+03:00",
      "type": "chat",
      "message_count": 500
    }
  ]
}
```

**Использование**: `DIALOG_ID` для группового чата = `chat` + `id`, например `chat153`.

---

## API: im.user.get

Получить данные пользователя по ID.

**URL**: `${BITRIX24_WEBHOOK_URL}im.user.get.json`

**Параметры**:
- `ID` — **обязательный**, ID пользователя

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.user.get.json" \
  -d 'ID=42'
```

**Ключевые поля ответа**:
```json
{
  "result": {
    "id": 42,
    "name": "Иванов Иван",
    "first_name": "Иван",
    "last_name": "Иванов",
    "work_position": "Менеджер",
    "avatar": "https://...",
    "status": "online"
  }
}
```

---

## API: im.chat.get

Получить данные группового чата по ID.

**URL**: `${BITRIX24_WEBHOOK_URL}im.chat.get.json`

**Параметры**:
- `CHAT_ID` — **обязательный**, числовой ID чата (без префикса `chat`)

**Шаблон**:
```bash
source .env && curl -s "${BITRIX24_WEBHOOK_URL}im.chat.get.json" \
  -d 'CHAT_ID=153'
```

**Ключевые поля ответа**:
```json
{
  "result": {
    "id": 153,
    "name": "Проект ABC",
    "owner": 1,
    "type": "chat",
    "date_create": "2025-01-05T09:00:00+03:00",
    "message_count": 500
  }
}
```

---

## Формат вывода

Подсказки для отображения результатов (адаптируй под контекст запроса):

**Список чатов** — таблица:
```
| Собеседник/Чат     | Последнее сообщение          | Дата       | Непрочитано |
|--------------------|------------------------------|------------|-------------|
| Иванов Иван        | Да, сделаю сегодня          | 15.01 14:30 | 3          |
| Проект ABC          | Отчёт готов                 | 15.01 15:00 | —          |
```

**Переписка** — хронологически с автором и датой:
```
[15.01 14:20] Иванов Иван: Привет, как дела с отчётом?
[15.01 14:25] Вы: Почти готово, отправлю через час
[15.01 14:30] Иванов Иван: Да, сделаю сегодня
```

**Поиск пользователя/чата** — краткий список результатов с ID.
