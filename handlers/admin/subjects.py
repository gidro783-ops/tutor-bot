# -*- coding: utf-8 -*-
"""Админка: раздел «Предметы» (добавление через FSM)."""
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import db
from keyboards.admin_kb import admin_subjects_menu, back_button
from keyboards.subscription_kb import cancel_flow_kb
from utils.helpers import escape_html, is_cancel

from .core import check_admin

logger = logging.getLogger(__name__)
router = Router()

class AddSubject(StatesGroup):
    name = State()
    price = State()
    description = State()

# =================== ПРЕДМЕТЫ ===================
@router.callback_query(F.data == "admin:subjects")
async def admin_subjects(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📚 <b>Предметы</b>",
        reply_markup=admin_subjects_menu(),
    )
@router.callback_query(F.data == "admin:subjects:list")
async def admin_subjects_list(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    subjects_list = await db.get_subjects()
    if not subjects_list:
        await callback.message.edit_text(
            "📭 Предметов нет.",
            reply_markup=back_button("admin:subjects"),
        )
        return
    text = "📚 <b>Предметы:</b>\n\n"
    for s in subjects_list:
        status = "✅" if s.get("is_active") else "❌"
        text += f"{status} {escape_html(s['name'])} — {s.get('price_per_hour', 0)}₽/ч\n"
    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:subjects"),
    )
@router.callback_query(F.data == "admin:subjects:add")
async def admin_add_subject(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    await state.set_state(AddSubject.name)
    await callback.message.edit_text(
        "📚 Название предмета:", reply_markup=cancel_flow_kb()
    )
@router.message(AddSubject.name)
async def add_subject_name(message: Message, state: FSMContext):
    if is_cancel(message.text):
        await state.clear()
        await message.answer("❌ Добавление предмета отменено.")
        return
    name = message.text.strip()
    if not name or len(name) > 200:
        await message.answer("❌ Название от 1 до 200 символов:")
        return
    await state.update_data(name=name)
    await state.set_state(AddSubject.price)
    await message.answer("💰 Цена за час (число):")
@router.message(AddSubject.price)
async def add_subject_price(message: Message, state: FSMContext):
    from utils.helpers import validate_amount
    if is_cancel(message.text):
        await state.clear()
        await message.answer("❌ Добавление предмета отменено.")
        return
    try:
        price = validate_amount(message.text)
    except ValueError as e:
        await message.answer(f"❌ {e}\n\nЕщё раз:")
        return
    await state.update_data(price=price)
    await state.set_state(AddSubject.description)
    await message.answer("📋 Описание (или «-» без описания):")
@router.message(AddSubject.description)
async def add_subject_description(message: Message, state: FSMContext):
    data = await state.get_data()
    desc = "" if message.text.strip() == "-" else message.text.strip()
    try:
        await db.add_subject(name=data["name"], price=data["price"], description=desc)
        await state.clear()
        await message.answer(f"✅ Предмет <b>{escape_html(data['name'])}</b> добавлен!")
    except Exception as e:
        logger.error(f"Failed to add subject: {e}")
        await state.clear()
        await message.answer("❌ Ошибка. Возможно, предмет уже существует.")
