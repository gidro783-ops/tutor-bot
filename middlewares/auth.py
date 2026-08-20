from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database import db
import logging
logger = logging.getLogger(__name__)
class DndMiddleware(BaseMiddleware):
    """Мидлвар для режима «Не беспокоить».
    
    ИСПРАВЛЕНО: раньше DND отправлял автоответ, 
    но всё равно пропускал handler. Теперь — блокирует.
    """
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
        try:
            is_dnd, auto_reply = await db.is_dnd_active()
        except Exception as e:
            logger.error(f"[DndMiddleware] Failed to check DND: {e}")
            is_dnd = False
        if is_dnd:
            try:
                await event.answer(auto_reply)
            except Exception as e:
                logger.warning(f"[DndMiddleware] Failed to send auto-reply: {e}")
            # ИСПРАВЛЕНО: НЕ пропускаем handler — DND значит "не беспокоить"
            return
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
            try:
                student = await db.get_student(user_id)
                if student:
                    await db.update_student_activity(user_id)
            except Exception as e:
                logger.error(f"[ActivityMiddleware] Failed for user {user_id}: {e}")
        return await handler(event, data)
