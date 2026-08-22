# -*- coding: utf-8 -*-
"""Админка: раздел «Расписание»."""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import db
from keyboards.admin_kb import admin_schedule_menu, back_button
from utils.helpers import format_date

from .core import check_admin

router = Router()

# =================== РАСПИСАНИЕ ===================
@router.callback_query(F.data == "admin:schedule")
async def admin_schedule(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "📅 <b>Расписание</b>",
        reply_markup=admin_schedule_menu(),
    )
@router.callback_query(F.data == "admin:schedule:today")
async def admin_schedule_today(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    from datetime import date as date_type
    today = date_type.today().isoformat()
    slots = await db.get_slots_for_date(today)
    if not slots:
        await callback.message.edit_text(
            f"📭 На сегодня ({format_date(today)}) слотов нет.",
            reply_markup=back_button("admin:schedule"),
        )
        return
    text = f"📅 <b>Сегодня ({format_date(today)}):</b>\n\n"
    for s in slots:
        status = "✅" if s["is_available"] else "🔒"
        text += f"{status} {s['start_time'][:5]}—{s['end_time'][:5]}\n"
    await callback.message.edit_text(
        text,
        reply_markup=back_button("admin:schedule"),
    )
