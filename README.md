# Bitrix Bot

Claude Code и Codex skills для работы с Битрикс24 через CLI: задачи, чаты, дайджесты и обзоры активности.

## Что внутри

- Скиллы для **Claude Code** лежат в `.claude/skills/`
- Скиллы для **Codex** лежат в `.agents/skills/`
- Основной доступ к Bitrix24 идёт через **входящий вебхук** в `.env`
- Часть обзоров использует локальные Python-скрипты из `.claude/scripts/`

Важно: это **репозиторий со скиллами**, а не отдельное приложение. Ничего "устанавливать в Claude/Codex" вручную не нужно, если вы запускаете агент **внутри этой папки**.

## Требования

- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)** — CLI-инструмент от Anthropic
- **Подписка Claude** — Pro ($20/мес) или Max ($100/$200/мес)
- **Codex** — десктоп‑клиент или CLI от OpenAI (опционально)
- **Битрикс24** — корпоративный портал с доступом к REST API
- **Python 3** — для встроенных скриптов обзоров и диагностики

## Быстрый старт

### 1. Установить клиент

#### Claude Code

```bash
npm install -g @anthropic-ai/claude-code
claude
```

При первом запуске откроется браузер для входа в аккаунт Anthropic.

#### Codex

Скиллы работают и в [Codex](https://developers.openai.com/codex/cli/) от OpenAI.

macOS:

- десктоп-приложение: <https://persistent.oaistatic.com/codex-app-prod/Codex.dmg>
- CLI через Homebrew:

```bash
brew install codex
```

Windows:

```bash
npm install -g @openai/codex
```

Для Windows рекомендуется WSL.

### 2. Клонировать репозиторий

```bash
git clone https://github.com/elstatic/bitrix-bot.git
cd bitrix-bot
```

Если проект нужен прямо в текущей папке:

```bash
git clone https://github.com/elstatic/bitrix-bot.git .
```

### 3. Подготовить окружение

Самый быстрый путь:

```bash
./scripts/bootstrap.sh
```

Скрипт:

- проверит, что рядом есть `python3`, `claude` и/или `codex`
- создаст `.env` из `.env.example`, если файла ещё нет
- подскажет, что заполнить дальше

После этого откройте `.env` и задайте:

```bash
export BITRIX24_WEBHOOK_URL="https://ваш-домен.bitrix24.ru/rest/USER_ID/WEBHOOK_CODE/"
```

`PROJECTS_DIRS` — опционально. Если его нет, обзоры по локальным проектам просто пропустят git-сканирование.

### 4. Создать вебхук Битрикс24

1. Откройте Битрикс24: **Приложения** → **Разработчикам** → **Другое** → **Входящий вебхук**
2. Выберите права:
   - `task` — задачи
   - `im` — чаты
   - `calendar` — встречи
   - `user` — профиль
   - `crm` — опционально
3. Сохраните и скопируйте URL вида:

```text
https://ваш-домен.bitrix24.ru/rest/USER_ID/WEBHOOK_CODE/
```

### 5. Проверить окружение

```bash
./scripts/doctor.sh
```

Скрипт проверит базовые зависимости, `.env`, доступность webhook и опциональные функции вроде Google Workspace.

### 6. Запустить агента в этой папке

Claude Code:

```bash
claude
```

Codex:

```bash
codex
```

Примеры запросов:

```text
покажи мои задачи в битриксе
обзор дня
что писали в чате
```

## Как это работает

Claude Code автоматически подхватывает скиллы из `.claude/skills/`.

Codex автоматически подхватывает скиллы из `.agents/skills/`, если вы запускаете Codex **внутри этого репозитория**.

Из-за этого репозиторий удобно шарить коллегам как обычную папку проекта: клонировали, настроили `.env`, запустили своего агента внутри папки.

## Какие скиллы доступны

### Общие для Claude и Codex

| Скилл | Что делает | Как вызвать |
|-------|-----------|-------------|
| **bitrix24-tasks** | Просмотр, создание, обновление задач | «покажи мои задачи», «создай задачу» |
| **bitrix24-task-changes** | Дедлайн, комментарии, трудозатраты, история | «поменяй дедлайн», «добавь 2 часа», «напиши в задачу» |
| **bitrix24-chats** | Чтение чатов и переписок | «покажи чаты», «что писали в чате» |
| **daily-review** | Сводка за день: чаты, задачи, встречи, git | «обзор дня», «что нового» |
| **project-overview** | Обзор проекта: метрика, конверсии, задачи | «обзор проекта», «как дела у проекта» |
| **setup-env** | Настройка вебхука и `.env` | «настроить окружение» |
| **weekly-review** | Сводка за неделю + git-активность | «обзор недели», «итоги недели» |

### Только в Codex

| Скилл | Что делает |
|-------|-----------|
| **chat-digest** | Сжатый дайджест переписок |
| **department-review** | Отчёт по отделу и подчинённым |

### Только в Claude Code

| Скилл | Что делает |
|-------|-----------|
| **bitrix24-chat-search** | Поиск по сообщениям Bitrix24 |
| **google-workspace** | Работа с Google Sheets, Drive, Docs и Apps Script |

## Google Workspace (опционально)

Скилл `google-workspace` нужен не всем. Для него, кроме Python 3, требуются отдельные пакеты и OAuth-клиент.

Установка зависимостей:

```bash
pip3 install -r requirements-google-workspace.txt
```

Дальше:

1. Подготовьте OAuth client credentials
2. Положите файл туда, куда указывает `GOOGLE_OAUTH_CLIENT_PATH`, или используйте путь по умолчанию `.claude/google-oauth-client.json`
3. Выполните:

```bash
python3 .claude/scripts/google_workspace/gw.py auth
```

## Быстрые сборщики

Daily Review использует оптимизированный сборщик:

```bash
python3 .claude/scripts/daily_review/main.py --yesterday
```

Оптимизации:

- Batch API Bitrix24
- параллельные запросы
- кеш чатов на 24 часа в `~/.cache/daily-review/chat-digest/`

## Структура

```text
.claude/
  skills/         # скиллы для Claude Code
  scripts/        # локальные Python-скрипты для обзоров и интеграций
  agents/         # вспомогательные агенты Claude
  rules/          # дополнительные правила
.agents/
  skills/         # скиллы для Codex
scripts/
  bootstrap.sh    # первый запуск
  doctor.sh       # проверка окружения
AGENTS.md         # инструкции для агентов в Codex
README.md         # инструкция для людей
```

## Полезно знать

- Если в `.env` уже есть `BITRIX24_WEBHOOK_URL`, отдельный сетап не нужен
- `PROJECTS_DIRS` можно не задавать
- Для Codex и Claude наборы скиллов частично отличаются
- Если запускаете агента не из этой папки, автоподхват локальных скиллов может не сработать

## Безопасность

- `.env` с вебхуком не коммитится
- `*.local.json` и кэши локальных токенов не должны попадать в git
- вебхук привязан к конкретному сотруднику
- при увольнении сотрудника вебхук нужно отключить в Bitrix24
