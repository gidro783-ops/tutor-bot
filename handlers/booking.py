from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from keyboards.student_kb import (
    subject_selection, date_selection, time_selection,
    booking_confirm, booking_type_selection, student_main_menu
)
from utils.texts import Texts
from utils.helpers import format_date, escape_html
from config import config
import logging
logger = logging.getLogger(__name__)
router = Router()
class BookingFlow(StatesGroup):
    choosing_type = State()
    choosing_subject = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()
async def start_booking(message: Message, state: FSMContext):
    """Начало процесса записи."""
    await state.set_state(BookingFlow.choosing_type)
    await message.answer(
        "📅 Выберите тип занятия:",
        reply_markup=booking_type_selection()
    )
@router.callback_query(F.data.startswith("book:type:"))
async def choose_booking_type(callback: CallbackQuery, state: FSMContext):
    booking_type = callback.data.split(":")[-1]
    await state.update_data(booking_type=booking_type)
    await state.set_state(BookingFlow.choosing_subject)
    subjects = await db.get_subjects()
    if not subjects:
        await callback.message.edit_text(
            "😔 Предметы ещё не добавлены. Свяжитесь с репетитором."
        )
        await state.clear()
        return
    type_text = "🆓 Пробное занятие" if booking_type == "trial" else "📚 Обычное занятие"
    await callback.message.edit_text(
        f"{type_text}\n\n📚 Выберите предмет:",
        reply_markup=subject_selection(subjects)
    )
@router.callback_query(F.data.startswith("book:subject:"))
async def choose_subject(callback: CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.split(":")[-1])
    subject = await db.get_subject(subject_id)
    await state.update_data(
        subject_id=subject_id,
        subject_name=subject["name"] if subject else "—"
    )
    await state.set_state(BookingFlow.choosing_date)
    slots = await db.get_available_slots()
    if not slots:
        await callback.message.edit_text(Texts.NO_AVAILABLE_SLOTS)
        await state.clear()
        return
    await callback.message.edit_text(
        Texts.BOOKING_CHOOSE_DATE,
        reply_markup=date_selection(slots)
    )
@router.callback_query(F.data.startswith("book:date:"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    date_str = callback.data.split(":")[-1]
    await state.update_data(date=date_str)
    await state.set_state(BookingFlow.choosing_time)
    all_slots = await db.get_available_slots()
    day_slots = [s for s in all_slots if s["date"] == date_str]
    if not day_slots:
        await callback.message.edit_text(
            f"😔 На {format_date(date_str)} нет свободных слотов."
        )
        return
    await callback.message.edit_text(
        f"📅 {format_date(date_str)}\n\n{Texts.BOOKING_CHOOSE_TIME}",
        reply_markup=time_selection(day_slots)
    )
@router.callback_query(F.data.startswith("book:slot:"))
async def choose_slot(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split(":")[-1])
    slot = await db.get_slot(slot_id)
    if not slot or not slot["is_available"]:
        await callback.answer("❌ Этот слот уже занят!", show_alert=True)
        return
    data = await state.get_data()
    await state.update_data(
        slot_id=slot_id,
        start_time=slot["start_time"],
        end_time=slot["end_time"]
    )
    await state.set_state(BookingFlow.confirming)
    booking_type_text = (
        "🆓 Пробное" if data.get("booking_type") == "trial"
        else "📚 Обычное"
    )
    text = (
        f"✅ Подтвердите запись:\n\n"
        f"📚 Предмет: {escape_html(data.get('subject_name', '—'))}\n"
        f"📅 Дата: {format_date(data.get('date', ''))}\n"
        f"🕐 Время: {slot['start_time'][:5]} — {slot['end_time'][:5]}\n"
        f"📝 Тип: {booking_type_text}\n\n"
        f"Всё верно?"
    )
    await callback.message.edit_text(text, reply_markup=booking_confirm())
@router.callback_query(F.data == "book:confirm")
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    """ИСПРАВЛЕНО: атомарная блокировка слота вместо race condition."""
    data = await state.get_data()
    user_id = callback.from_user.id
    slot_id = data["slot_id"]
    # ===== АТОМАРНАЯ БЛОКИРОВКА СЛОТА =====
    # UPDATE + проверка is_available=1 в одном запросе
    cursor = await db.db.execute(
        "UPDATE time_slots SET is_available = 0 WHERE id = ? AND is_available = 1",
        (slot_id,)
    )
    affected = cursor.rowcount
    await db.db.commit()
    if affected == 0:
        # Слот уже занят кем-то другим
        await callback.message.edit_text(
            "❌ К сожалению, этот слот уже занят. Выберите другое время."
        )
        await state.clear()
        return
    # Слот заблокирован — создаём бронирование
    try:
        booking_id = await db.create_booking(
            student_id=user_id,
            slot_id=slot_id,
            subject_id=data.get("subject_id"),
            booking_type=data.get("booking_type", "trial")
        )
    except Exception as e:
        # Если бронирование не удалось — вернуть слот
        await db.db.execute(
            "UPDATE time_slots SET is_available = 1 WHERE id = ?",
            (slot_id,)
        )
        await db.db.commit()
        logger.error(f"Booking creation failed for slot {slot_id}: {e}")
        await callback.message.edit_text("❌ Ошибка при записи. Попробуйте позже.")
        await state.clear()
        return
    # Логируем воронку (ИСПРАВЛЕНА опечатка funnel → funnel)
    event_type = (
        "trial_booked" if data.get("booking_type") == "trial"
        else "regular_booked"
    )
    await db.log_funnel_event(user_id, event_type)
    await state.clear()
    text = (
        f"🎉 Вы успешно записаны!\n\n"
        f"📚 {escape_html(data.get('subject_name', '—'))}\n"
        f"📅 {format_date(data.get('date', ''))} в {data.get('start_time', '')[:5]}\n\n"
        f"Я напомню вам о занятии заранее. До встречи!"
    )
    await callback.message.edit_text(text)
    # Уведомляем админа (ИСПРАВЛЕНО: логируем ошибки вместо silent pass)
    student = await db.get_student(user_id)
    for admin_id in config.ADMIN_IDS:
        try:
            booking_type_text = (
                "🆓 ПРОБНОЕ" if data.get("booking_type") == "trial"
                else "📚 Обычное"
            )
            await callback.bot.send_message(
                admin_id,
                f"🔔 Новая запись!\n\n"
                f"👤 {escape_html(student['full_name'] if student else '—')} "
                f"(@{escape_html(callback.from_user.username or '—')})\n"
                f"📚 {escape_html(data.get('subject_name', '—'))}\n"
                f"📅 {format_date(data.get('date', ''))}\n"
                f"🕐 {data.get('start_time', '')[:5]}\n"
                f"📝 Тип: {booking_type_text}\n"
                f"🆔 Запись #{booking_id}"
            )
        except Exception as e:
            logger.error(f"[confirm_booking] Failed to notify admin {admin_id}: {e}")
@router.callback_query(F.data == "book:cancel")
async def cancel_booking_flow(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена.")
@router.callback_query(F.data == "book:back_to_subject")
async def back_to_subject(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingFlow.choosing_subject)
    subjects = await db.get_subjects()
    await callback.message.edit_text(
        "📚 Выберите предмет:",
        reply_markup=subject_selection(subjects)
    )
@router.callback_query(F.data == "book:back_to_date")
async def back_to_date(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingFlow.choosing_date)
    slots = await db.get_available_slots()
    await callback.message.edit_text(
        Texts.BOOKING_CHOOSE_DATE,
        reply_markup=date_selection(slots)
    )
