# Weekly Review Script

Python-скрипт для генерации еженедельного обзора активности с использованием:
- **Batch API Bitrix24** для максимальной скорости (3-4 запроса вместо 30+)
- **asyncio** для параллельных операций
- **Субагент chat-digest** для суммаризации чатов (вызывается из skill)

## Установка

### 1. Установить зависимости

```bash
cd .claude/scripts/weekly_review
pip3 install -r requirements.txt
```

### 2. Настроить .env

Добавить в `.env` в корне проекта:

```bash
# Обязательные переменные
export BITRIX24_WEBHOOK_URL="https://team.up-advert.ru/rest/1535/CODE/"

# Опционально
export PROJECTS_DIRS="~/projects"      # Папки с git-проектами
```

**Примечание:** Суммаризация чатов делается субагентом `chat-digest`, который вызывается из skill отдельно.

## Использование

### Текущая неделя (по умолчанию)

```bash
python3 .claude/scripts/weekly_review/main.py
```

### Прошлая неделя

```bash
python3 .claude/scripts/weekly_review/main.py --week last
```

### Произвольный период

```bash
python3 .claude/scripts/weekly_review/main.py --from 2026-01-20 --to 2026-01-27
```

### Отладка

```bash
python3 .claude/scripts/weekly_review/main.py --week last --debug
```

## Что собирает

1. **Задачи Bitrix24** (через batch API):
   - Созданные за неделю
   - Назначенные за неделю
   - Закрытые за неделю
   - Активные задачи

2. **Встречи** (из календаря Bitrix24)

3. **Трудозатраты** (через batch API)

4. **Git активность** (из локальных проектов):
   - Коммиты за период
   - Статистика изменений

**Примечание:** Чаты собираются отдельно через субагент `chat-digest` в skill.

## Оптимизация

### Batch API

Скрипт использует batch API для минимизации HTTP-запросов:

| Компонент | Было (curl) | Стало (batch) | Ускорение |
|-----------|-------------|---------------|-----------|
| Задачи | 4 запроса | 1 batch | 4x |
| Трудозатраты | N запросов | 1 batch | Nx |
| Чаты | Последовательно | Async parallel | 3-5x |
| Git | Последовательно | Async parallel | 2x |
| **Итого** | **~30-60 сек** | **~5-10 сек** | **3-6x** |

### Кеширование

Список проектов кешируется на 24 часа в `~/.cache/weekly-review/projects-cache.json`

## Graceful Degradation

Если одна из секций не загрузилась (ошибка API, отсутствие данных и т.д.), остальные продолжают работать. Пустые секции не показываются в финальном отчёте.

## Архитектура

```
main.py                     # Entry point, CLI orchestration
config.py                   # Конфигурация из .env
models.py                   # Dataclasses
date_utils.py               # Утилиты для дат

api/
  bitrix_client.py          # Async Bitrix24 client с batch
  claude_client.py          # Claude API для суммаризации
  batch_builder.py          # Helper для batch запросов

analyzers/
  tasks.py                  # Сбор задач через batch
  meetings.py               # Встречи
  chats.py                  # Чаты + суммаризация
  git.py                    # Git активность
  time_tracking.py          # Анализ трудозатрат

formatters/
  markdown.py               # Markdown форматтер
  stats.py                  # Расчёт статистики

cache.py                    # Кеш-утилиты
```

## Интеграция со skill

Skill `.claude/skills/weekly-review/SKILL.md` вызывает этот скрипт вместо curl команд.

## Требования

- Python 3.8+
- aiohttp >= 3.9.0
- python-dotenv >= 1.0.0
- anthropic >= 0.18.0
