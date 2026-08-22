# -*- coding: utf-8 -*-
"""Автоудаление служебных сообщений бота.

Промпты ввода, запросы кодов, подтверждения и ошибки живут в чате
MESSAGE_TTL_MINUTES минут (по умолчанию 3) и исчезают сами — чат
не засоряется. Содержательные сообщения (ответы ИИ, списки занятий,
счета, меню) не удаляются никогда. 0 в .env = выключить автоудаление.
"""
from __future__ import annotations

import asyncio
import logging

from config import config

logger = logging.getLogger(__name__)


def auto_delete(message, minutes: float | None = None) -> None:
    """Удалить сообщение бота через `minutes` (по умолчанию — из .env).

    Безопасно: ошибки удаления (сообщение старше 48 ч, уже удалено и
    т.п.) молча игнорируются.
    """
    if message is None:
        return
    ttl = config.MESSAGE_TTL_MINUTES if minutes is None else minutes
    if ttl <= 0:
        return

    async def _delete_later():
        await asyncio.sleep(ttl * 60)
        try:
            await message.bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass  # уже удалено / слишком старое / нет прав — не критично

    try:
        asyncio.get_running_loop().create_task(_delete_later())
    except RuntimeError:
        logger.warning("auto_delete: нет запущенного event loop")


async def say(message, *args, **kwargs):
    """message.answer + автоудаление: `await say(message, "текст")`.

    Для служебных сообщений (промпты, подтверждения, ошибки).
    """
    sent = await message.answer(*args, **kwargs)
    auto_delete(sent)
    return sent
