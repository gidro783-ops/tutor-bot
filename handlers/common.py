# -*- coding: utf-8 -*-
"""Общие хендлеры: /cancel и кнопка «❌ Отмена» для любых сценариев ввода.

Роутер подключается ПЕРВЫМ — команда /cancel перехватывается до
сценариев (FSM-шаги, Step-флоу из fixes.py) и гарантированно выводит
пользователя из любого ввода.
"""
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger(__name__)
router = Router()


async def _finish(message_or_cb, state: FSMContext):
    await state.clear()
    text = "❌ Ввод отменён."
    if isinstance(message_or_cb, CallbackQuery):
        await message_or_cb.answer("Отменено")
        try:
            if message_or_cb.message:
                await message_or_cb.message.edit_text(text)
        except Exception:
            pass  # сообщение старое/недоступно — не критично
    else:
        await message_or_cb.answer(text)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data and (await state.get_state()) is None:
        await message.answer("Нечего отменять 🙂")
        return
    await _finish(message, state)


@router.callback_query(F.data == "cancel_flow")
async def cancel_flow(callback: CallbackQuery, state: FSMContext):
    await _finish(callback, state)
