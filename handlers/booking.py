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
from utils.helpers import format_date
from config import config

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
        f"{type_text}\n\n{Texts.BOOKING_CHOOSE_SUBJECT}",
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

    text = Texts.BOOKING_CONFIRM.format(
        subject=data.get("subject_name", "—"),
        date=format_date(data.get("date", "")),
        start_time=slot["start_time"][:5],
        end_time=slot["end_time"][:5],
        booking_type=booking_type_text
    )

    await callback.message.edit_text(text, reply_markup=booking_confirm())


@router.callback_query(F.data == "book:confirm")
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id

    # Проверяем, не занят ли слот
    slot = await db.get_slot(data["slot_id"])
    if not slot or not slot["is_available"]:
        await callback.message.edit_text(
            "❌ К сожалению, этот слот уже занят. Выберите другое время."
        )
        await state.clear()
        return

    # Создаём бронирование
    booking_id = await db.create_booking(
        student_id=user_id,
        slot_id=data["slot_id"],
        subject_id=data.get("subject_id"),
        booking_type=data.get("booking_type", "trial")
    )

    # Логируем в воронку
    event_type = (
        "trial_booked" if data.get("booking_type") == "trial"
        else "regular_booked"
    )
    await db.log_funnel_event(user_id, event_type)

    await state.clear()

    text = Texts.BOOKING_SUCCESS.format(
        subject=data.get("subject_name", "—"),
        date=format_date(data.get("date", "")),
        start_time=data.get("start_time", "")[:5]
    )

    await callback.message.edit_text(text)

    # Уведомляем админа
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
                f"👤 {student['full_name'] if student else '—'} "
                f"(@{callback.from_user.username or '—'})\n"
                f"📚 {data.get('subject_name', '—')}\n"
                f"📅 {format_date(data.get('date', ''))}\n"
                f"🕐 {data.get('start_time', '')[:5]}\n"
                f"📝 Тип: {booking_type_text}\n"
                f"🆔 Запись #{booking_id}"
            )
        except Exception:
            pass


@router.callback_query(F.data == "book:cancel")
async def cancel_booking_flow(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Запись отменена.")


@router.callback_query(F.data == "book:back_to_subject")
async def back_to_subject(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingFlow.choosing_subject)
    subjects = await db.get_subjects()
    await callback.message.edit_text(
        Texts.BOOKING_CHOOSE_SUBJECT,
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