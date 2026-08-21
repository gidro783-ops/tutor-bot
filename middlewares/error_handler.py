"""Глобальный обработчик ошибок aiogram.

Без него любое необработанное исключение в хэндлере «вешает» бота:
пользователю показывается крутилка, а сообщение не приходит.
Этот middleware ловит исключения на уровне DP и отвечает пользователю,
не краша обработчик.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import ErrorEvent, Message

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[ErrorEvent, Dict[str, Any]], Awaitable[Any]],
        event: ErrorEvent,
        data: Dict[str, Any],
    ) -> Any:
        exc = event.exception
        update = event.update

        # Логируем с контекстом (кто и какой апдейт сломал)
        user_id = None
        chat_id = None
        try:
            if update.message and update.message.from_user:
                user_id = update.message.from_user.id
                chat_id = update.message.chat.id
        except Exception:
            pass

        logger.error(
            "Поймана необработанная ошибка: %s: %s | user=%s chat=%s",
            type(exc).__name__,
            exc,
            user_id,
            chat_id,
            exc_info=exc,
        )

        # Пытаемся мягко ответить пользователю вместо «тишины»
        try:
            if update.message:
                await update.message.answer(
                    "❌ Произошла внутренняя ошибка. Попробуйте ещё раз чуть позже."
                )
            elif update.callback_query and update.callback_query.message:
                await update.callback_query.answer(
                    "❌ Ошибка. Нажмите /start и попробуйте снова.", show_alert=True
                )
        except Exception:
            # Даже ответ не ушёл (нет прав/чат удалён) — просто не падаем
            pass

        # Уведомляем админов (критично для отладки)
        if user_id:
            try:
                from config import config

                bot = data.get("bot")
                if bot:
                    for admin_id in config.ADMIN_IDS:
                        try:
                            await bot.send_message(
                                admin_id,
                                f"🔥 Ошибка у пользователя <code>{user_id}</code>:\n"
                                f"<code>{type(exc).__name__}: {exc}</code>",
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass
            except Exception:
                pass

        return None
