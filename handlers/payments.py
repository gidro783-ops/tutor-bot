from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards.student_kb import payment_keyboard
from utils.helpers import escape_html, validate_amount
from config import config
import logging
from services.cleanup import say
logger = logging.getLogger(__name__)
router = Router()
class CreatePaymentAdmin(StatesGroup):
    student_id = State()
    amount = State()
    description = State()
# =================== УЧЕНИК: просмотр оплат ===================
@router.message(F.text == "💳 Оплата")
async def my_payments_menu(message: Message):
    payments = await db.get_pending_payments(message.from_user.id)
    # ИСПРАВЛЕНИЕ: показываем и счета со статусом 'reported'
    # («Я оплатил» нажат, ждём подтверждения репетитора)
    reported = await db.get_reported_payments(message.from_user.id)
    if not payments and not reported:
        await message.answer("✅ Нет неоплаченных счетов!")
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    text = "💳 <b>Ваши счета:</b>\n\n"
    for p in payments:
        text += f"• #{p['id']} {p['amount']}₽ — {escape_html(p.get('description', ''))}\n"
        builder.button(text=f"✅ Я оплатил #{p['id']}", callback_data=f"payment:paid:{p['id']}")
    for p in reported:
        text += (
            f"• ⏳ #{p['id']} {p['amount']}₽ — оплата сообщена, "
            f"ждём подтверждения от репетитора\n"
        )
    if builder.buttons:
        builder.adjust(1)
        await message.answer(text, reply_markup=builder.as_markup())
    else:
        await message.answer(text)
@router.callback_query(F.data.startswith("payment:view:"))
async def view_payment(callback: CallbackQuery):
    pay_id = int(callback.data.split(":")[-1])
    payment = await db.get_payment_by_id(pay_id)
    if not payment:
        await callback.answer("Не найдено", show_alert=True)
        return
    text = (
        f"💳 <b>Счёт #{pay_id}</b>\n\n"
        f"💰 Сумма: {payment['amount']}₽\n"
        f"📋 Описание: {escape_html(payment.get('description', '—'))}\n"
        f"📅 Создан: {payment['created_at'][:10]}\n"
        f"📊 Статус: {payment['status']}"
    )
    await callback.message.edit_text(text)
# =================== АДМИН: создать счёт ===================
@router.callback_query(F.data == "admin:pay:create")
async def admin_create_payment_start(callback: CallbackQuery, state: FSMContext):
    students_list = await db.get_all_students()
    if not students_list:
        await callback.answer("Нет учеников", show_alert=True)
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for s in students_list[:20]:
        builder.button(
            text=f"👤 {s['full_name'][:30]}",
            callback_data=f"admin:pay:to:{s['user_id']}"
        )
    builder.button(text="◀️ Назад", callback_data="admin:payments")
    builder.adjust(1)
    await callback.message.edit_text(
        "👤 Выберите ученика:",
        reply_markup=builder.as_markup()
    )
@router.callback_query(F.data.startswith("admin:pay:to:"))
async def admin_pay_select_student(callback: CallbackQuery, state: FSMContext):
    student_id = int(callback.data.split(":")[-1])
    await state.update_data(student_id=student_id)
    await state.set_state(CreatePaymentAdmin.amount)
    await callback.message.edit_text("💰 Введите сумму (число):")
@router.message(CreatePaymentAdmin.amount)
async def admin_pay_amount(message: Message, state: FSMContext):
    try:
        amount = validate_amount(message.text)
    except ValueError as e:
        await say(message, f"❌ {e}\n\nВведите сумму ещё раз:")
        return
    await state.update_data(amount=amount)
    await state.set_state(CreatePaymentAdmin.description)
    await say(message, "📋 Введите описание (или «-» без описания):")
@router.message(CreatePaymentAdmin.description)
async def admin_pay_description(message: Message, state: FSMContext):
    desc = "" if message.text.strip() == "-" else message.text.strip()
    data = await state.get_data()
    try:
        cursor = await db.db.execute(
            """INSERT INTO payments (student_id, amount, description, status)
               VALUES (?, ?, ?, 'pending')""",
            (data["student_id"], data["amount"], desc)
        )
        await db.db.commit()
        pay_id = cursor.lastrowid
        await state.clear()
        # Уведомляем ученика
        try:
            await message.bot.send_message(
                data["student_id"],
                f"💳 <b>Новый счёт на оплату</b>\n\n"
                f"💰 Сумма: {data['amount']}₽\n"
                + (f"📋 {escape_html(desc)}" if desc else "")
            )
        except Exception as e:
            logger.warning(f"Failed to notify student about payment: {e}")
        await say(message, f"✅ Счёт #{pay_id} создан: {data['amount']}₽")
    except Exception as e:
        logger.error(f"Failed to create payment: {e}")
        await state.clear()
        await say(message, "❌ Ошибка при создании счёта.")
# =================== АДМИН: отметить оплаченным ===================
@router.callback_query(F.data.startswith("admin:pay:mark:"))
async def admin_mark_paid(callback: CallbackQuery):
    # ИСПРАВЛЕНИЕ: теперь доступна только админу (раньше её мог нажать
    # любой ученик и пометить чужой счёт оплаченным)
    from handlers.admin import check_admin
    if not await check_admin(callback):
        return
    pay_id = int(callback.data.split(":")[-1])
    payment = await db.get_payment_by_id(pay_id)
    if not payment or payment.get("status") not in ("pending", "reported"):
        await callback.answer("Счёт не найден или уже оплачен", show_alert=True)
        return
    try:
        # ИСПРАВЛЕНИЕ: подтверждаем и 'pending', и 'reported'
        await db.confirm_payment(pay_id, method="admin_confirmed")
        await callback.message.edit_text(f"✅ Счёт #{pay_id} отмечен как оплаченный.")
        # Уведомляем ученика, что оплата подтверждена
        try:
            await callback.bot.send_message(
                payment["student_id"],
                f"🎉 <b>Оплата подтверждена!</b>\n\n"
                f"Счёт #{pay_id} на {payment['amount']}₽ закрыт.\n"
                f"Спасибо! Ждём вас на занятии 📚"
            )
        except Exception as e:
            logger.warning(f"[admin_mark_paid] notify student: {e}")
    except Exception as e:
        logger.error(f"Failed to mark payment as paid: {e}")
        await callback.answer("Ошибка", show_alert=True)
# =================== АДМИН: статистика оплат ===================
@router.callback_query(F.data == "admin:pay:stats")
async def admin_pay_stats(callback: CallbackQuery):
    try:
        stats = await db.get_payment_stats()
        text = (
            f"📊 <b>Статистика оплат (30 дней)</b>\n\n"
            f"✅ Получено: {stats.get('total_paid', 0):.0f}₽\n"
            f"⏳ Ожидается: {stats.get('total_pending', 0):.0f}₽\n"
            f"📊 Оплаченных счетов: {stats.get('paid_count', 0)}\n"
            f"📋 Неоплаченных: {stats.get('pending_count', 0)}"
        )
        from keyboards.admin_kb import back_button
        await callback.message.edit_text(
            text,
            reply_markup=back_button("admin:payments"),
        )
    except Exception as e:
        logger.error(f"Payment stats error: {e}")
        await callback.answer("Ошибка", show_alert=True)
# =================== АДМИН: история оплат ===================
@router.callback_query(F.data == "admin:pay:history")
async def admin_pay_history(callback: CallbackQuery):
    try:
        all_payments = await db.get_all_payments()
        if not all_payments:
            await callback.message.edit_text(
                "📭 История оплат пуста.",
                reply_markup=back_btn()
            )
            return
        text = "✅ <b>История оплат:</b>\n\n"
        for p in all_payments[:20]:
            text += f"💳 {p['amount']}₽ — {escape_html(p.get('description', '')[:30])} ✅\n"
        from keyboards.admin_kb import back_button
        await callback.message.edit_text(
            text,
            reply_markup=back_button("admin:payments"),
        )
    except Exception as e:
        logger.error(f"Payment history error: {e}")
        await callback.answer("Ошибка", show_alert=True)
def back_btn():
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="admin:payments")
    return builder.as_markup()
