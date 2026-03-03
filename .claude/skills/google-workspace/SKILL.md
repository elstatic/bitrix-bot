---
name: google-workspace
description: "Работа с Google Sheets, Drive, Docs и Apps Script. Активируется при упоминании: гугл таблица, google sheets, гугл диск, google drive, гугл документ, google docs, google apps script, GAS, скрипт гугл"
---

# Google Workspace Skill

Работа с Google Sheets, Drive, Docs и Apps Script через OAuth2 (аккаунт пользователя).

## Авторизация

OAuth2 от реального пользователя Google. Токен кешируется локально.

**Файлы:**
- Client credentials: `.claude/google-oauth-client.json` (путь в `.env` → `GOOGLE_OAUTH_CLIENT_PATH`)
- Кешированный токен: `.claude/google-oauth-token.json` (создаётся автоматически)

**Первый запуск:**
1. `python3 .claude/scripts/google_workspace/gw.py auth`
2. Откроется браузер → подтвердить доступ для приложения
3. Токен сохранится в `.claude/google-oauth-token.json`
4. Повторная авторизация не нужна (токен обновляется автоматически)

Скоупы:
- `spreadsheets` — чтение/запись Google Sheets
- `drive` — файлы Google Drive
- `documents` — Google Docs
- `script.projects` — Google Apps Script

## CLI-интерфейс

```bash
python3 .claude/scripts/google_workspace/gw.py <command> [subcommand] [args]
```

Вывод — **всегда JSON**. Ошибки — JSON в stderr.

## Команды

### auth — проверка авторизации

```bash
python3 .claude/scripts/google_workspace/gw.py auth
```

### sheets — Google Sheets

```bash
# Прочитать данные (весь лист или диапазон)
python3 .claude/scripts/google_workspace/gw.py sheets read <spreadsheet_id>
python3 .claude/scripts/google_workspace/gw.py sheets read <spreadsheet_id> "Sheet1!A1:D10"

# Записать данные
python3 .claude/scripts/google_workspace/gw.py sheets write <spreadsheet_id> "Sheet1!A1:B2" '[["a","b"],["c","d"]]'

# Метаданные таблицы (листы, размеры)
python3 .claude/scripts/google_workspace/gw.py sheets info <spreadsheet_id>
```

### drive — Google Drive

```bash
# Список файлов (опционально: query в формате Drive API, drive-id для Shared Drive)
python3 .claude/scripts/google_workspace/gw.py drive list
python3 .claude/scripts/google_workspace/gw.py drive list --query "mimeType='application/vnd.google-apps.spreadsheet'"
python3 .claude/scripts/google_workspace/gw.py drive list --drive-id <shared_drive_id>

# Поиск по имени
python3 .claude/scripts/google_workspace/gw.py drive search "отчёт"

# Метаданные файла
python3 .claude/scripts/google_workspace/gw.py drive info <file_id>
```

### docs — Google Docs

```bash
# Прочитать текст документа
python3 .claude/scripts/google_workspace/gw.py docs read <document_id>

# Создать документ (опционально: в папку)
python3 .claude/scripts/google_workspace/gw.py docs create "Новый документ"
python3 .claude/scripts/google_workspace/gw.py docs create "Отчёт" --folder <folder_id>
```

### gas — Google Apps Script

```bash
# Список standalone GAS-проектов
python3 .claude/scripts/google_workspace/gw.py gas list

# Найти container-bound скрипт таблицы (по URL или ID)
python3 .claude/scripts/google_workspace/gw.py gas bound <spreadsheet_url_or_id>

# Получить файлы проекта по script_id
python3 .claude/scripts/google_workspace/gw.py gas get <script_id>

# Обновить файлы проекта
python3 .claude/scripts/google_workspace/gw.py gas update <script_id> '[{"name":"Code","type":"SERVER_JS","source":"function main() {}"}]'
```

**Работа с container-bound скриптами:**
Пользователь даёт ссылку на таблицу → `gas bound` находит привязанный скрипт → возвращает scriptId и все файлы с кодом. Далее scriptId используется для `gas get` / `gas update`. Не нужно открывать редактор скриптов вручную.

**Типовой workflow редактирования GAS:**
1. `gas bound <URL>` → получить scriptId и все файлы
2. Изменить нужный код
3. `gas update <scriptId> '<JSON>'` — загрузить обновлённые файлы (ВАЖНО: передавать ВСЕ файлы проекта включая `appsscript`, не только изменённый)

**Создание container-bound скрипта:**
Через Script API `projects.create` с `parentId` = ID таблицы.

**Триггеры:**
Нельзя создать удалённо через API. Нужно добавить функцию-установщик в код (например `setupDailyTrigger_xxx()` с `ScriptApp.newTrigger(...).timeBased()...`) и попросить пользователя запустить её один раз из редактора.

## Важные замечания

1. OAuth2 работает от имени пользователя — доступ ко **всем** файлам пользователя без расшаривания.
2. **Shared Drive** — пользователь должен быть участником диска.
3. **Apps Script API** должен быть включён в Google Cloud проекте.
4. **Запись в Sheets** использует `USER_ENTERED` — формулы и форматы дат обрабатываются автоматически.

## Как получить spreadsheet_id

Из URL таблицы: `https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`

## Как получить document_id

Из URL документа: `https://docs.google.com/document/d/<DOCUMENT_ID>/edit`
