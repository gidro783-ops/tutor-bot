"""FSM-гарда: выход из любого состояния ввода по кнопке «❌ Отмена».

Проблема: в aiogram любое FSM-состояние (например, ввод цены или пароля)
перехватывает сообщения, и нажатие кнопки меню/Отмены может «проглотиться»
состоянием без ответа.

Этот middleware ставится на роутер(ы) с FSM-вводом и:
1) реагирует на callback «cancel» из инлайн-клавиатур;
2) передаёт сообщения дальше, если пользователь нажал кнопку меню
   или ввёл /команду — тогда состояние сбрасывается.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.types import CallbackQuery, Message

CANCEL_DATA = {"cancel", "cancel:"}
# Эти слова сбрасывают любой ввод, даже если хэндлер состояния молчит
CANCEL_WORDS = {"отмена", "cancel", "❌ отмена", "отменить"}

# Кнопки главного меню пользователя — их нажатие должно мгновенно
# вытаскивать из любого сценария ввода
MENU_BUTTONS = {
    "📅 записаться",
    "📋 мои занятия",
    "🤖 спросить ии",
    "📝 домашние задания",
    "💳 оплата",
    "❓ faq",
    "🎁 пригласить друга",
    "👤 профиль",
    "📞 связаться с репетитором",
}


class FsmGuard(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        state: FSMContext = data.get("state")

        # Если нет активного состояния — просто пропускаем
        if not isinstance(state, FSMContext):
            return await handler(event, data)

        current = await state.get_state()
        if current is None:
            return await handler(event, data)

        # ---------- CALLBACK-отмена ----------
        if isinstance(event, CallbackQuery):
            payload = (event.data or "").strip()
            if payload in CANCEL_DATA:
                await state.clear()
                try:
                    await event.answer("❌ Отменено")
                except Exception:
                    pass
                # Если была создана инлайн-кнопка рядом с текстом — убираем
                try:
                    if event.message:
                        from aiogram.types import InlineKeyboardMarkup
                        await event.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
                return

        # ---------- MESSAGE-отмена ----------
        if isinstance(event, Message):
            text = (event.text or "").strip().lower()

            # /команда или кнопка меню → сбрасываем состояние и отдаём хэндлеру
            if text.startswith("/") or text in MENU_BUTTONS:
                await state.clear()
                return await handler(event, data)

            # Текст «отмена» внутри любого состояния
            if text in CANCEL_WORDS:
                await state.clear()
                await event.answer("❌ Ввод отменён.")
                return

        return await handler(event, data)
