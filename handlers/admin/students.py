# -*- coding: utf-8 -*-
"""Админка: раздел «Ученики»."""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import db
from keyboards.admin_kb import (
    admin_students_menu,
    back_button,
    student_detail_keyboard,
    student_list_keyboard,
)
from keyboards.subscription_kb import cancel_flow_kb
from utils.helpers import escape_html

from .core import check_admin

router = Router()


class PackageStates(StatesGroup):
    count = State()

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
    & ~F.data.contains(":report:")
    & ~F.data.contains(":package:")
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
        f"🎟 Абонемент: {student.get('lessons_balance', 0)} занятий\n"
        f"💳 Долг: {len(pending_payments)}\n"
        f"📝 {escape_html(student.get('notes', '—'))}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=student_detail_keyboard(student_id),
    )


# =================== ОТЧЁТ ПО УЧЕНИКУ (файлом) ===================
@router.callback_query(F.data.startswith("admin:student:report:"))
async def student_report(callback: CallbackQuery):
    """Полная карточка ученика одним текстовым файлом."""
    if not await check_admin(callback):
        return
    from aiogram.types import BufferedInputFile

    student_id = int(callback.data.split(":")[-1])
    student = await db.get_student(student_id)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return
    bookings = await db.get_student_bookings(student_id)
    homework = await db.get_student_homework(student_id)
    payments = await db.get_pending_payments(student_id)

    completed = [b for b in bookings if b["status"] == "completed"]
    paid_total = 0
    try:
        cursor = await db.db.execute(
            "SELECT COALESCE(SUM(amount), 0) AS s FROM payments"
            " WHERE student_id = ? AND status = 'paid'",
            (student_id,)
        )
        paid_total = (await cursor.fetchone())["s"]
    except Exception:
        pass

    lines = [
        f"ОТЧЁТ ПО УЧЕНИКУ: {student['full_name']}",
        f"Telegram ID: {student['user_id']}",
        f"Телефон: {student.get('phone') or '—'}",
        f"Источник: {student.get('source') or '—'}",
        f"Зарегистрирован: {str(student.get('registration_date', ''))[:19]}",
        "",
        f"Занятий всего: {len(bookings)} (проведено: {len(completed)})",
        "",
        "=== БУДУЩИЕ И ПРОШЛЫЕ ЗАНЯТИЯ ===",
    ]
    for b in bookings[:30]:
        lines.append(
            f"{str(b.get('date', ''))[:10]} {str(b.get('start_time', ''))[:5]}"
            f" — {b.get('status')} {b.get('subject_name') or ''}"
        )
    lines += ["", "=== ДОМАШНИЕ ЗАДАНИЯ ==="]
    for h in homework[:30]:
        lines.append(
            f"#{h['id']} {str(h.get('title'))[:50]} — {h.get('status')}"
            f" (оценка: {h.get('grade') or '—'})"
        )
    lines += ["", f"=== ОПЛАТА ===", f"Всего оплачено: {paid_total:.0f} ₽",
              f"Неоплаченных счетов: {len(payments)}"]
    for pay in payments:
        lines.append(f"  #{pay['id']} {pay['amount']:.0f} ₽ — {pay.get('description', '')}")

    content = "\n".join(lines).encode("utf-8")
    await callback.answer()
    await callback.message.answer_document(
        BufferedInputFile(content, filename=f"student_{student_id}.txt"),
        caption=f"📄 Отчёт: {escape_html(student['full_name'])}",
    )


# =================== АБОНЕМЕНТЫ (пакеты занятий) ===================
@router.callback_query(F.data.startswith("admin:student:package:"))
async def sell_package(callback: CallbackQuery, state: FSMContext):
    """Продать абонемент: количество занятий и цена."""
    if not await check_admin(callback):
        return
    student_id = int(callback.data.split(":")[-1])
    student = await db.get_student(student_id)
    if not student:
        await callback.answer("Ученик не найден", show_alert=True)
        return
    await state.update_data(student_id=student_id)
    await state.set_state(PackageStates.count)
    balance = int(student.get("lessons_balance") or 0)
    await callback.message.edit_text(
        f"🎟 <b>Абонемент для {escape_html(student['full_name'])}</b>\n"
        f"Остаток сейчас: {balance}\n\n"
        f"Введите: <code>количество;цена</code>\n"
        f"Например: <code>8;7200</code> (8 занятий за 7200 ₽)",
        reply_markup=cancel_flow_kb(),
    )


@router.message(PackageStates.count)
async def save_package(message: Message, state: FSMContext):
    from services.cleanup import say
    from utils.helpers import is_cancel, validate_amount

    if is_cancel(message.text):
        await state.clear()
        await say(message, "❌ Продажа абонемента отменена.")
        return
    raw = (message.text or "").replace(" ", "")
    try:
        count_str, _, price_str = raw.partition(";")
        count = int(count_str)
        price = validate_amount(price_str)
        assert 1 <= count <= 100
    except Exception:
        await say(message, "❌ Формат: количество;цена (например 8;7200):")
        return
    data = await state.get_data()
    await state.clear()
    student = await db.get_student(data["student_id"])
    if not student:
        await say(message, "❌ Ученик не найден.")
        return
    new_balance = await db.add_lessons(student["user_id"], count)
    await db.create_payment(
        student["user_id"], price,
        f"Абонемент: {count} занятий",
    )
    # счёт абонемента закрываем сразу как оплаченный (продажа вручную)
    try:
        cursor = await db.db.execute(
            "SELECT id FROM payments WHERE student_id = ? AND description = ?"
            " ORDER BY id DESC LIMIT 1",
            (student["user_id"], f"Абонемент: {count} занятий"),
        )
        row = await cursor.fetchone()
        if row:
            await db.confirm_payment(row["id"], method="package")
    except Exception:
        pass
    await say(
        message,
        f"🎟 Абонемент продан: +{count} занятий ({price:.0f} ₽).\n"
        f"Остаток {escape_html(student['full_name'])}: {new_balance}.",
    )
    try:
        await message.bot.send_message(
            student["user_id"],
            f"🎟 <b>Абонемент активирован!</b>\n\n"
            f"Занятий на балансе: {new_balance}\n"
            f"Оплачено: {price:.0f} ₽\n\n"
            f"Приходите на занятие — баланс уменьшится сам.",
        )
    except Exception:
        pass
