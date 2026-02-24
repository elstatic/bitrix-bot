---
name: bitrix24-chat-search
description: "Поиск чатов, чтение и отправка сообщений Битрикс24. Активируется при: найди чат, поиск в чатах, найди переписку, отправь сообщение в чат, напиши в чат, send message b24"
---

# Bitrix24 Chat Search Skill

Скрипт `.claude/scripts/chat_search/main.py` — поиск чатов, чтение и отправка сообщений через Bitrix24 REST API.

**Stdlib only.** Конфиг загружается из `.env` автоматически.

## Субкоманды

### 1. find-chat — поиск чатов и пользователей

```bash
python3 .claude/scripts/chat_search/main.py find-chat "запрос"
```

Сначала пробует `im.search.chat.list` + `im.search.user.list` через batch.
Если пусто (баг FIND_SHORT с кириллицей) — фолбэк на `im.recent.list` с фильтрацией.

Возвращает JSON массив: `[{id, dialog_id, title, type, ...}]`

### 2. messages — чтение сообщений

```bash
# Последние N сообщений
python3 .claude/scripts/chat_search/main.py messages chat58841 --limit 50

# Поиск по тексту
python3 .claude/scripts/chat_search/main.py messages chat58841 --text "отчёт"

# По датам
python3 .claude/scripts/chat_search/main.py messages chat58841 --from 2026-02-01 --to 2026-02-08
```

Возвращает JSON массив: `[{id, author, author_id, text, date}]`

### 3. send — отправка сообщения

```bash
python3 .claude/scripts/chat_search/main.py send chat58841 "Текст сообщения"
```

Возвращает JSON: `{success, message_id}`

## ВАЖНО: подтверждение перед отправкой

**ВСЕГДА** перед вызовом `send` спрашивай подтверждение у пользователя через AskUserQuestion:

```
Отправить сообщение в [название чата]?

> [текст сообщения]
```

Никогда не отправляй сообщения без явного подтверждения.

## Отладка

Добавь `--debug` для отладочного вывода в stderr:

```bash
python3 .claude/scripts/chat_search/main.py --debug find-chat "стратегический"
```

## Формат вывода для пользователя

**Результаты поиска чатов:**
```
Найдено N чатов:
1. [тип] «Название» — dialog_id: chatXXXXX
2. [user] «Имя Фамилия» — dialog_id: 42
```

**Сообщения:**
```
[15.01 14:20] Иванов Иван: Привет, как дела с отчётом?
[15.01 14:25] Петров Пётр: Почти готово
```

**Отправка:**
```
Сообщение отправлено (ID: 12345)
```
