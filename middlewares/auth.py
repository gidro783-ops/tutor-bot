from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database import db


class DndMiddleware(BaseMiddleware):
    """Мидлвар для режима «Не беспокоить»."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        from config import config

        # Пропускаем админов
        if event.from_user and event.from_user.id in config.ADMIN_IDS:
            return await handler(event, data)

        # Пропускаем команды
        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        # Проверяем DND
        is_dnd, auto_reply = await db.is_dnd_active()
        if is_dnd:
            await event.answer(auto_reply)
            # Всё равно обрабатываем, но с флагом
            data["is_dnd"] = True

        return await handler(event, data)


class ActivityMiddleware(BaseMiddleware):
    """Мидлвар для обновления активности пользователя."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        if event.from_user:
            user_id = event.from_user.id
            student = await db.get_student(user_id)
            if student:
                await db.update_student_activity(user_id)

        return await handler(event, data)