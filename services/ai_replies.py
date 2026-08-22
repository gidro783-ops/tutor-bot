# -*- coding: utf-8 -*-
"""ИИ-автоответы в личных сообщениях репетитора (через userbot).

Репетитор включает автоответы в админке (🤖 ИИ-ассистент → ✉️ Автоответы
в ЛС). После этого входящие ЛС на реальный аккаунт репетитора получает
ИИ и отвечает от его лица — по анкете и FAQ (см. services/ai_assistant).

Защита от ложных срабатываний:
- список исключений (@username / ID) — друзья, семья и т.п.;
- если репетитор САМ ответил человеку — ИИ молчит в этом чате 24 часа;
- кулдаун между автоответами одному человеку (60 сек);
- боты, команды, стикеры и группы игнорируются;
- лимиты тарифа: Free — 10 ответов ИИ в день (общий счётчик с ботом),
  PRO — безлимит.
"""
from __future__ import annotations

import json
import logging
import time

from config import config
from database import db

logger = logging.getLogger(__name__)

DM_ENABLED_KEY = "ai_dm_enabled"
SKIP_LIST_KEY = "ai_skip_list"

COOLDOWN_SEC = 60          # пауза между автоответами одному человеку
MANUAL_PAUSE_SEC = 24 * 3600  # молчание после ручного ответа репетитора

# runtime-состояние (в памяти; перезапуск бота сбрасывает паузы)
_attached = False
_last_auto: dict[int, float] = {}     # chat_id → время последнего автоответа
_manual_at: dict[int, float] = {}     # chat_id → время последнего ручного ответа


# =================== ИСКЛЮЧЕНИЯ (@username / ID) ===================

async def get_skip_list() -> list[dict]:
    try:
        raw = await db.get_setting(SKIP_LIST_KEY, "[]")
        items = json.loads(raw)
        return [i for i in items if isinstance(i, dict)]
    except Exception:
        return []


async def add_skip(user_id: int | None, username: str | None) -> None:
    items = await get_skip_list()
    username = (username or "").strip().lstrip("@").lower() or None
    for i in items:
        if (user_id is not None and i.get("id") == user_id) or (
            username and i.get("username") == username
        ):
            return  # уже в списке
    items.append({"id": user_id, "username": username})
    await db.set_setting(SKIP_LIST_KEY, json.dumps(items, ensure_ascii=False))


async def remove_skip(index: int) -> None:
    items = await get_skip_list()
    if 0 <= index < len(items):
        items.pop(index)
        await db.set_setting(SKIP_LIST_KEY, json.dumps(items, ensure_ascii=False))


def is_excluded(sender_id: int | None, username: str | None, skip: list[dict]) -> bool:
    """Чистая функция: человек в списке исключений?"""
    uname = (username or "").strip().lstrip("@").lower()
    for item in skip:
        if sender_id is not None and item.get("id") == sender_id:
            return True
        if uname and item.get("username") and uname == item["username"]:
            return True
    return False


# =================== РЕШЕНИЕ «ОТВЕЧАТЬ ИЛИ НЕТ» ===================

def should_auto_reply(
    *,
    dm_enabled: bool,
    ai_configured: bool,
    is_private: bool,
    sender_is_bot: bool,
    text: str,
    excluded: bool,
    cooldown_left: float,
    manual_pause_left: float,
    quota_left: int | None,
) -> tuple[bool, str]:
    """Чистая функция: нужен ли автоответ (и почему нет). Тестируется."""
    if not dm_enabled:
        return False, "disabled"
    if not ai_configured:
        return False, "not_configured"
    if not is_private:
        return False, "not_private"
    if sender_is_bot:
        return False, "sender_is_bot"
    if excluded:
        return False, "excluded"
    text = (text or "").strip()
    if not text or text.startswith("/"):
        return False, "no_text"
    if cooldown_left > 0:
        return False, "cooldown"
    if manual_pause_left > 0:
        return False, "manual_pause"
    if quota_left is not None and quota_left <= 0:
        return False, "quota"
    return True, "ok"


# =================== TELETHON-ХЕНДЛЕРЫ ===================

def attach(client) -> None:
    """Повесить обработчики на клиент userbot (один раз)."""
    global _attached
    if _attached or client is None:
        return
    from telethon import events

    client.add_event_handler(_on_incoming, events.NewMessage(incoming=True))
    client.add_event_handler(_on_outgoing, events.NewMessage(outgoing=True))
    _attached = True
    logger.info("AI DM auto-replies attached to userbot")


async def _pause_left(chat_id: int) -> float:
    ts = _manual_at.get(chat_id)
    if ts is None:
        return 0.0
    return max(0.0, MANUAL_PAUSE_SEC - (time.time() - ts))


async def _on_outgoing(event):
    """Ручной ответ репетитора = ИИ молчит в этом чате 24 часа.

    Автоисключаем собственные автоответы (они тоже исходящие): если
    секунду назад здесь отвечал ИИ — это не ручной ответ.
    """
    try:
        if not event.is_private:
            return
        chat_id = event.chat_id
        last = _last_auto.get(chat_id)
        if last is not None and time.time() - last < 10:
            return  # это наш автоответ, не трогаем
        _manual_at[chat_id] = time.time()
    except Exception as e:
        logger.warning("ai_replies outgoing: %s", e)


async def _on_incoming(event):
    try:
        dm_enabled = await db.get_setting(DM_ENABLED_KEY, "0") == "1"
        if not dm_enabled:
            return
        from services import ai_assistant, subscription as sub_service

        if not config.AI_API_KEY or not await ai_assistant.is_configured():
            return
        if not event.is_private:
            return

        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False):
            return

        sender_id = getattr(sender, "id", None)
        username = getattr(sender, "username", None)
        skip = await get_skip_list()
        excluded = is_excluded(sender_id, username, skip)

        chat_id = event.chat_id
        last = _last_auto.get(chat_id)
        cooldown_left = max(0.0, COOLDOWN_SEC - (time.time() - last)) if last else 0.0

        owner = config.ADMIN_IDS[0] if config.ADMIN_IDS else None
        quota_left = None
        if owner is not None:
            quota_left = await sub_service.ai_answers_left_today(owner)

        ok, reason = should_auto_reply(
            dm_enabled=True,
            ai_configured=True,
            is_private=True,
            sender_is_bot=False,
            text=event.message.message or "",
            excluded=excluded,
            cooldown_left=cooldown_left,
            manual_pause_left=await _pause_left(chat_id),
            quota_left=quota_left,
        )
        if not ok:
            if reason in ("excluded", "manual_pause"):
                logger.debug("AI reply skipped (%s) for %s", reason, chat_id)
            elif reason == "quota":
                logger.info("AI reply skipped: free quota exhausted")
            return

        answer = await ai_assistant.answer_question(event.message.message or "")
        await event.reply(answer)
        _last_auto[chat_id] = time.time()
        if owner is not None:
            await sub_service.consume_ai_answer(owner)
        logger.info("AI auto-reply sent to %s", chat_id)
    except Exception as e:
        logger.error("ai_replies incoming failed: %s", e)
