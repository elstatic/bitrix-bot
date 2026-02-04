# UP Advert Bot

Claude Code skills для работы с Битрикс24: задачи, чаты, обзоры дня и недели.

## Быстрый старт

### 1. Установить Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

### 2. Клонировать репозиторий

```bash
git clone git@github.com:elstatic/up_advert_bot.git
cd up_advert_bot
```

### 3. Создать вебхук Битрикс24

1. Открыть Битрикс24: **Приложения** → **Разработчикам** → **Другое** → **Входящий вебхук**
   - Прямая ссылка: `https://team.up-advert.ru/devops/edit/webhook/`
2. Выбрать нужные **права доступа** (scopes):
   - `task` — задачи
   - `im` — мессенджер (чаты)
   - `calendar` — календарь (встречи)
   - `user` — пользователи (для profile)
   - `crm` — CRM (опционально)
3. Нажать **Сохранить**
4. Скопировать URL вебхука — он будет вида:
   ```
   https://team.up-advert.ru/rest/ВАША_ID/ВАША_СЕКРЕТНАЯ_ЧАСТЬ/
   ```

### 4. Настроить окружение

```bash
claude
```

В Claude Code выполнить команду:

```
/setup-env
```

Или создать файл `.env` вручную:

```bash
echo 'export BITRIX24_WEBHOOK_URL="https://team.up-advert.ru/rest/YOUR_ID/YOUR_CODE/"' > .env
```

### 5. Проверить

В Claude Code:

```
покажи мои задачи в битриксе
```

## Доступные скиллы

| Скилл | Что делает | Как вызвать |
|-------|-----------|-------------|
| **bitrix24-tasks** | Просмотр, создание, обновление задач | «покажи мои задачи», «создай задачу» |
| **bitrix24-task-changes** | Дедлайн, комментарии, трудозатраты, история | «поменяй дедлайн», «добавь 2 часа», «напиши в задачу» |
| **bitrix24-chats** | Чтение чатов и переписок | «покажи чаты», «что писали в чате» |
| **daily-review** | Сводка за день: чаты, задачи, встречи | «обзор дня», «что нового» |
| **weekly-review** | Сводка за неделю + git-активность | «обзор недели», «итоги недели» |
| **setup-env** | Настройка вебхука | «настроить окружение» |

## Структура

```
.claude/
├── skills/
│   ├── bitrix24-tasks/SKILL.md
│   ├── bitrix24-task-changes/SKILL.md
│   ├── bitrix24-chats/SKILL.md
│   ├── daily-review/SKILL.md
│   ├── weekly-review/SKILL.md
│   └── setup-env/SKILL.md
├── agents/
│   ├── activity-data-collector.md
│   └── project-activity-digest.md
└── rules/
    └── subagents.md
```

## Безопасность

- `.env` с вебхуком **не коммитится** (в `.gitignore`)
- `*.local.json` с локальными настройками **не коммитятся**
- Вебхук привязан к конкретному пользователю — не передавайте его третьим лицам
- При увольнении сотрудника — деактивируйте его вебхук в Битрикс24
