# Quick Start

## 1️⃣ Установка (один раз)

```bash
cd /Users/elstatic/projects/up_advert_bot/.claude/scripts/weekly_review
pip3 install -r requirements.txt
```

## 2️⃣ Настройка .env

Убедитесь что в `.env` есть:

```bash
export BITRIX24_WEBHOOK_URL="https://team.up-advert.ru/rest/..."
export PROJECTS_DIRS="~/projects"  # опционально
```

**API ключи не нужны!** Суммаризация чатов делается через субагент.

## 3️⃣ Использование

### Прошлая неделя (понедельник-воскресенье):

```bash
cd /Users/elstatic/projects/up_advert_bot
source .env && python3 .claude/scripts/weekly_review/main.py --week last
```

### Текущая неделя (понедельник-сегодня):

```bash
cd /Users/elstatic/projects/up_advert_bot
source .env && python3 .claude/scripts/weekly_review/main.py --week current
```

### Через Claude Code skill:

```
/weekly-review
```

---

## Что делает скрипт?

✅ Собирает задачи из Bitrix24 (созданные, закрытые, активные)
✅ Загружает встречи из календаря
✅ Подсчитывает трудозатраты
✅ Сканирует git-активность в локальных проектах

**Примечание:** Чаты суммаризуются отдельно через субагент `chat-digest` в skill.

**Скорость**: 5-15 секунд (в 3-6 раз быстрее оригинального подхода)

---

## Troubleshooting

**ModuleNotFoundError: aiohttp**
→ Выполните шаг 1️⃣ (установка зависимостей)

**BITRIX24_WEBHOOK_URL не задан**
→ Добавьте URL вебхука в .env

**Долго выполняется**
→ Добавьте `--debug` чтобы увидеть, что тормозит

---

Полная документация: [README.md](README.md) | Верификация: [VERIFICATION.md](VERIFICATION.md)
