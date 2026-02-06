"""Claude API клиент для суммаризации чатов."""

import sys
from typing import List, Dict, Any, Optional
import aiohttp

from ..models import DialogSummary


class ClaudeClient:
    """Асинхронный клиент для Claude API."""

    API_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-sonnet-4-5-20250929"

    def __init__(self, api_key: str, debug: bool = False):
        """
        Инициализация клиента.

        Args:
            api_key: API ключ Anthropic
            debug: Включить отладочный вывод
        """
        self.api_key = api_key
        self.debug = debug
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Создать сессию при входе в контекст."""
        self.session = aiohttp.ClientSession(
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрыть сессию при выходе из контекста."""
        if self.session:
            await self.session.close()

    def _log(self, message: str):
        """Вывести отладочное сообщение."""
        if self.debug:
            print(f"[ClaudeClient] {message}", file=sys.stderr)

    def _build_summarization_prompt(
        self,
        messages: List[Dict[str, Any]],
        user_name: str,
        dialog_name: str,
    ) -> str:
        """
        Построить промпт для суммаризации диалога.

        Args:
            messages: Список сообщений диалога
            user_name: Имя пользователя
            dialog_name: Название диалога

        Returns:
            Промпт для Claude
        """
        messages_text = "\n\n".join([
            f"[{msg.get('date', 'неизвестно')}] {msg.get('author_name', 'Неизвестный')}: {msg.get('text', '')}"
            for msg in messages
        ])

        return f"""Проанализируй переписку из Битрикс24 и составь краткую выжимку.

ДИАЛОГ: {dialog_name}
ПОЛЬЗОВАТЕЛЬ: {user_name}
КОЛИЧЕСТВО СООБЩЕНИЙ: {len(messages)}

СООБЩЕНИЯ:
{messages_text}

ЗАДАЧА:
Проанализируй диалог и выдели:
1. ТЕМА — одним предложением, о чём шла речь
2. ДОГОВОРЁННОСТИ — конкретные договорённости и решения (если есть)
3. РЕШЕНИЯ — принятые решения (если есть)
4. ВОПРОСЫ — открытые вопросы, требующие ответа (если есть)
5. ОЖИДАЕТ РЕАКЦИИ — нужно ли пользователю {user_name} что-то сделать или ответить

ФОРМАТ ОТВЕТА (строго JSON):
{{
  "topic": "краткая тема диалога одним предложением",
  "agreements": ["договорённость 1", "договорённость 2"],
  "decisions": ["решение 1", "решение 2"],
  "questions": ["вопрос 1", "вопрос 2"],
  "awaits_response": true/false
}}

ВАЖНО:
- Если какой-то категории нет, указывай пустой массив []
- Формулируй тезисы кратко и по делу
- awaits_response=true только если именно {user_name} должен что-то сделать
- Отвечай ТОЛЬКО валидным JSON, без дополнительного текста"""

    async def summarize_dialog(
        self,
        dialog_id: str,
        dialog_name: str,
        messages: List[Dict[str, Any]],
        user_name: str,
    ) -> Optional[DialogSummary]:
        """
        Суммаризовать диалог через Claude API.

        Args:
            dialog_id: ID диалога
            dialog_name: Название диалога
            messages: Список сообщений
            user_name: Имя пользователя

        Returns:
            DialogSummary или None при ошибке
        """
        if not self.session:
            raise RuntimeError("Сессия не инициализирована. Используйте async with.")

        if not messages:
            return None

        self._log(f"Суммаризация диалога '{dialog_name}' ({len(messages)} сообщений)")

        prompt = self._build_summarization_prompt(messages, user_name, dialog_name)

        payload = {
            "model": self.MODEL,
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }

        try:
            async with self.session.post(self.API_URL, json=payload) as response:
                response.raise_for_status()
                data = await response.json()

                # Извлечь текст ответа
                content = data.get("content", [])
                if not content:
                    self._log(f"Пустой ответ от Claude для диалога {dialog_name}")
                    return None

                text = content[0].get("text", "")

                # Парсинг JSON из ответа
                import json
                try:
                    result = json.loads(text)
                except json.JSONDecodeError:
                    self._log(f"Не удалось распарсить JSON из ответа Claude: {text[:200]}")
                    return None

                return DialogSummary(
                    dialog_id=dialog_id,
                    dialog_name=dialog_name,
                    message_count=len(messages),
                    topic=result.get("topic", "Тема не определена"),
                    agreements=result.get("agreements", []),
                    decisions=result.get("decisions", []),
                    questions=result.get("questions", []),
                    awaits_response=result.get("awaits_response", False),
                )

        except aiohttp.ClientError as e:
            self._log(f"Ошибка HTTP запроса к Claude API: {e}")
            return None
        except Exception as e:
            self._log(f"Неожиданная ошибка при суммаризации: {e}")
            return None
