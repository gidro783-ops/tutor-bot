# -*- coding: utf-8 -*-
"""Админка: раздел «Ученики»."""
from aiogram import Router, F
from aiogram.types import CallbackQuery

from database import db
from keyboards.admin_kb import (
    admin_students_menu,
    back_button,
    student_detail_keyboard,
    student_list_keyboard,
)
from utils.helpers import escape_html

from .core import check_admin

router = Router()

# =================== УЧЕНИКИ ===================
@router.callback_query(F.data == "admin:students")
async def admin_students(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    await callback.message.edit_text(
        "👥 <b>Управление учениками</b>",
        reply_markup=admin_students_menu(),
    )
@router.callback_query(F.data == "admin:students:list")
async def admin_students_list(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    students_list = await db.get_all_students()
    if not students_list:
        await callback.message.edit_text(
            "📭 Учеников пока нет.",
            reply_markup=back_button("admin:students"),
        )
        return
    await callback.message.edit_text(
        f"👥 Всего учеников: {len(students_list)}",
        reply_markup=student_list_keyboard(students_list),
    )
@router.callback_query(F.data.startswith("admin:students:page:"))
async def admin_students_page(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    page = int(callback.data.split(":")[-1])
    students_list = await db.get_all_students()
    await callback.message.edit_text(
        f"👥 Всего учеников: {len(students_list)}",
        reply_markup=student_list_keyboard(students_list, page=page),
    )
@router.callback_query(
    F.data.startswith("admin:student:")
    & ~F.data.contains(":bookings")
    & ~F.data.contains(":hw")
    & ~F.data.contains(":payments")
    & ~F.data.contains(":message")
    & ~F.data.contains(":deactivate")
)
async def admin_student_detail(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    student_id = int(callback.data.split(":")[2])
    student = await db.get_student(student_id)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return
    bookings = await db.get_student_bookings(student_id)
    pending_payments = await db.get_pending_payments(student_id)
    text = (
        f"👤 <b>{escape_html(student['full_name'])}</b>\n\n"
        f"🆔 ID: <code>{student['user_id']}</code>\n"
        f"📱 @{escape_html(student.get('username') or '—')}\n"
        f"📞 {escape_html(student.get('phone') or '—')}\n"
        f"📅 {student['registration_date'][:10]}\n"
        f"📊 Занятий: {student.get('total_lessons', 0)}\n"
        f"📌 Источник: {student.get('source', '—')}\n"
        f"📋 Записей: {len(bookings)}\n"
        f"💳 Долг: {len(pending_payments)}\n"
        f"📝 {escape_html(student.get('notes', '—'))}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=student_detail_keyboard(student_id),
    )
