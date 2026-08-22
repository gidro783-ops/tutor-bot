# -*- coding: utf-8 -*-
"""ИИ-ассистент репетитора: отвечает ученикам от лица репетитора.

«Обучение» ИИ здесь — это не дообучение модели, а системная инструкция
(промпт), собираемая из анкеты репетитора (админка → 🤖 ИИ-ассистент)
и его FAQ. Любой OpenAI-совместимый API: DeepSeek, OpenAI, OpenRouter,
Groq, локальный Ollama — меняются AI_BASE_URL/AI_MODEL/AI_API_KEY в .env.
"""
from __future__ import annotations

import json
import logging

import aiohttp

from config import config
from database import db

logger = logging.getLogger(__name__)

# Ключи анкеты репетитора в bot_settings
KB_NAME = "ai_tutor_name"
KB_SUBJECTS = "ai_subjects"
KB_ABOUT = "ai_about"
KB_STYLE = "ai_style"
KB_ENABLED = "ai_enabled"

SYSTEM_TEMPLATE = """Ты — репетитор{tutor_name_part}, который переписывается в Telegram.
Ты не ассистент и не бот — это твой личный аккаунт, тон живого человека.

Как говорить:
- Пиши как обычный человек в мессенджере: коротко (1-4 предложения),
  разговорно, без канцелярита.
- БЕЗ эмодзи и смайликов. Без восклицательных знаков подряд.
- Не здоровайся при каждом сообщении («Здравствуйте»/«Привет» — только
  если человек написал впервые и ещё не получил ни одного ответа.
  В продолжении диалога сразу отвечай по делу, как в реальной переписке.
- Можно поддержать любую бытовую тему и маленький трёп, но по сути
  занятий, ценам, расписанию и условиям отвечай ТОЛЬКО по информации
  ниже — ничего не выдумывай и не обещай.
- Если нужного факта нет в информации — честно скажи, что уточнишь,
  и предложи уточнить детали (созвон/запись).
- Не сообщай телефоны, адреса и личные данные, кроме указанных ниже.

Информация о репетиторе и услугах:
{knowledge}{style_part}"""


def build_system_prompt(settings: dict, faq: list[dict]) -> str:
    """Собирает системный промпт из анкеты, FAQ и стиля (чистая функция).

    settings: {ai_tutor_name, ai_subjects, ai_about, ai_style}
    faq: [{"question", "answer"}, ...]
    """
    name = (settings.get(KB_NAME) or "").strip()
    subjects = (settings.get(KB_SUBJECTS) or "").strip()
    about = (settings.get(KB_ABOUT) or "").strip()
    style = (settings.get(KB_STYLE) or "").strip()

    tutor_name_part = f" {name}" if name else ""
    blocks = []
    if subjects:
        blocks.append(f"Предметы и цены:\n{subjects}")
    if about:
        blocks.append(f"Опыт, формат занятий, условия:\n{about}")
    if faq:
        faq_text = "\n".join(
            f"Вопрос: {str(f.get('question', '')[:200])}\n"
            f"Ответ: {str(f.get('answer', '')[:500])}"
            for f in faq[:20]
        )
        blocks.append(f"Частые вопросы (FAQ):\n{faq_text}")
    if not blocks:
        blocks.append(
            "(Анкета пока не заполнена. Общую информацию давай осторожно, "
            "детали обещай уточнить.)"
        )
    style_part = f"\n\nОсобый стиль общения (приоритетнее всего):\n{style}" if style else ""
    return SYSTEM_TEMPLATE.format(
        tutor_name_part=tutor_name_part,
        knowledge="\n\n".join(blocks),
        style_part=style_part,
    )


async def is_configured() -> bool:
    """ИИ готов отвечать: ключ есть и ассистент включён в админке."""
    if not config.AI_API_KEY:
        return False
    return await db.get_setting(KB_ENABLED, "0") == "1"


async def answer_question(question: str, history: list | None = None) -> str:
    """Спросить ИИ от лица репетитора. Бросает AiUnavailable при сбоях."""
    settings = {
        KB_NAME: await db.get_setting(KB_NAME, ""),
        KB_SUBJECTS: await db.get_setting(KB_SUBJECTS, ""),
        KB_ABOUT: await db.get_setting(KB_ABOUT, ""),
        KB_STYLE: await db.get_setting(KB_STYLE, ""),
    }
    try:
        faq = await db.get_all_faq()
    except Exception:
        faq = []
    system_prompt = build_system_prompt(settings, faq)

    messages = [{"role": "system", "content": system_prompt}]
    for m in (history or [])[-6:]:  # короткая память диалога
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": str(m["content"])[:2000]})
    messages.append({"role": "user", "content": question[:2000]})

    url = config.AI_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": config.AI_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 600,
    }
    headers = {
        "Authorization": f"Bearer {config.AI_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=40)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                body = await resp.text()
                if resp.status != 200:
                    logger.error("AI API %s: %s", resp.status, body[:300])
                    raise AiUnavailable(
                        "ИИ-сервис временно недоступен, попробуйте позже."
                    )
                data = json.loads(body)
                answer = data["choices"][0]["message"]["content"].strip()
                if not answer:
                    raise AiUnavailable("ИИ вернул пустой ответ.")
                return answer
    except AiUnavailable:
        raise
    except Exception as e:  # сеть, таймаут, формат ответа
        logger.error("AI request failed: %s", e)
        raise AiUnavailable("ИИ-сервис временно недоступен, попробуйте позже.")


class AiUnavailable(Exception):
    """ИИ не смог ответить (сеть/ключ/лимиты провайдера)."""
