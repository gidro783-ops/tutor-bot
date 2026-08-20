from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import db
from keyboards.student_kb import (
    student_main_menu, faq_keyboard, rating_keyboard
)
from utils.texts import Texts
from utils.helpers import generate_referral_code
from config import config

router = Router()


class ContactInfo(StatesGroup):
    phone = State()


class ReviewText(StatesGroup):
    text = State()
    booking_id = State()
    rating = State()


# =================== СТАРТ ===================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = message.from_user
    args = message.text.split(" ", 1)
    
    # 1. Проверяем, новый ли это ученик
    existing_student = await db.get_student(user.id)
    is_new_student = existing_student is None

    referrer_id = None
    source = "direct"
    source_chat_id = None

    # 2. Парсим аргументы из ссылки
    if len(args) > 1:
        param = args[1]
        if param.startswith("ref_"):
            try:
                referrer_id = int(param.replace("ref_", ""))
                source = "referral"
            except ValueError:
                pass
        elif param.startswith("chat_"):
            try:
                source_chat_id = int(param.replace("chat_", ""))
                source = "ad_chat"
                await db.increment_chat_leads(source_chat_id)
                await db.log_funnel_event(
                    user.id, "bot_started", source="ad_chat",
                    source_chat_id=source_chat_id
                )
            except ValueError:
                pass

    # 3. Регистрируем ученика (если его еще нет)
    await db.add_student(
        user_id=user.id,
        full_name=user.full_name or "Без имени",
        username=user.username,
        source=source,
        source_chat_id=source_chat_id,
        referrer_id=referrer_id
    )

    await db.log_funnel_event(user.id, "bot_started", source=source)

    # 4. Реферальная логика (ТОЛЬКО для новых и не для самого себя)
    if referrer_id and is_new_student and referrer_id != user.id:
        ref_code = generate_referral_code(user.id)
        is_new_referral = await db.create_referral(referrer_id, user.id, ref_code)
        
        if is_new_referral:
            referrer = await db.get_student(referrer_id)
            if referrer:
                text = Texts.WELCOME_REFERRAL.format(
                    name=user.first_name,
                    referrer=referrer["full_name"],
                    bonus=config.REFERRAL_BONUS_PERCENT
                )
            else:
                text = Texts.WELCOME.format(name=user.first_name)
        else:
            text = Texts.WELCOME.format(name=user.first_name)
    else:
        text = Texts.WELCOME.format(name=user.first_name)

    await state.clear()
    await message.answer(text, reply_markup=student_main_menu())
# =================== ОСНОВНОЕ МЕНЮ ===================

@router.message(F.text == "📅 Записаться на занятие")
async def book_lesson(message: Message, state: FSMContext):
    """Перенаправляем на хендлер записи."""
    from handlers.booking import start_booking
    await start_booking(message, state)


@router.message(F.text == "📋 Мои занятия")
async def my_lessons(message: Message):
    bookings = await db.get_student_bookings(
        message.from_user.id, status="confirmed"
    )
    if not bookings:
        await message.answer(
            "📭 У вас пока нет записей.\n\n"
            "Нажмите «📅 Записаться на занятие», чтобы выбрать время."
        )
        return

    from keyboards.student_kb import my_bookings_keyboard
    await message.answer(
        "📋 **Ваши занятия:**",
        reply_markup=my_bookings_keyboard(bookings),
        parse_mode="Markdown"
    )


@router.message(F.text == "📝 Домашние задания")
async def my_homework(message: Message):
    hw_list = await db.get_student_homework(message.from_user.id)
    if not hw_list:
        await message.answer("📭 Домашних заданий пока нет.")
        return

    from keyboards.student_kb import homework_list_keyboard
    await message.answer(
        "📝 **Ваши задания:**",
        reply_markup=homework_list_keyboard(hw_list),
        parse_mode="Markdown"
    )


@router.message(F.text == "💳 Оплата")
async def my_payments(message: Message):
    payments = await db.get_pending_payments(message.from_user.id)
    if not payments:
        await message.answer("✅ Нет неоплаченных счетов!")
        return

    text = "💳 **Неоплаченные счета:**\n\n"
    for p in payments:
        text += f"• {p['amount']}₽ — {p.get('description', '')}\n"

    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "❓ FAQ")
async def show_faq(message: Message):
    faqs = await db.get_all_faq()
    if not faqs:
        await message.answer(
            "❓ Раздел FAQ пока пуст.\n"
            "Напишите ваш вопрос — репетитор ответит лично!"
        )
        return

    await message.answer(
        "❓ **Частые вопросы:**\n\n"
        "Выберите интересующий вопрос:",
        reply_markup=faq_keyboard(faqs),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("faq:view:"))
async def view_faq(callback: CallbackQuery):
    faq_id = int(callback.data.split(":")[-1])
    faqs = await db.get_all_faq()
    faq = next((f for f in faqs if f["id"] == faq_id), None)
    if faq:
        await callback.message.edit_text(
            f"❓ **{faq['question']}**\n\n"
            f"{faq['answer']}",
            reply_markup=faq_keyboard(faqs),
            parse_mode="Markdown"
        )


@router.message(F.text == "🎁 Пригласить друга")
async def referral_info(message: Message):
    user_id = message.from_user.id
    stats = await db.get_referral_stats(user_id)
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    await message.answer(
        Texts.REFERRAL_INFO.format(
            link=link,
            bonus=config.REFERRAL_BONUS_PERCENT,
            total=stats["total_referrals"],
            completed=stats["completed"]
        )
    )


@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message):
    student = await db.get_student(message.from_user.id)
    if not student:
        await message.answer("Вы ещё не зарегистрированы. Нажмите /start")
        return

    bookings = await db.get_student_bookings(message.from_user.id)
    total = len(bookings)
    completed = len([b for b in bookings if b["status"] == "completed"])

    text = (
        f"👤 **Ваш профиль**\n\n"
        f"📛 Имя: {student['full_name']}\n"
        f"📱 Username: @{student.get('username', '—')}\n"
        f"📞 Телефон: {student.get('phone', 'Не указан')}\n"
        f"📅 Зарегистрирован: {student['registration_date'][:10]}\n"
        f"📊 Всего записей: {total}\n"
        f"✅ Проведено занятий: {completed}\n"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="📞 Указать телефон", callback_data="profile:phone")
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup(),
                         parse_mode="Markdown")


@router.callback_query(F.data == "profile:phone")
async def set_phone(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ContactInfo.phone)
    await callback.message.edit_text("📞 Введите ваш номер телефона:")


@router.message(ContactInfo.phone)
async def process_phone(message: Message, state: FSMContext):
    await db.update_student(message.from_user.id, phone=message.text)
    await state.clear()
    await message.answer(
        "✅ Телефон сохранён!",
        reply_markup=student_main_menu()
    )


@router.message(F.text == "📞 Связаться с репетитором")
async def contact_tutor(message: Message):
    # Отправляем уведомление админу
    for admin_id in config.ADMIN_IDS:
        try:
            student = await db.get_student(message.from_user.id)
            name = student["full_name"] if student else message.from_user.full_name
            await message.bot.send_message(
                admin_id,
                f"📞 Ученик хочет связаться!\n\n"
                f"👤 {name}\n"
                f"🆔 ID: {message.from_user.id}\n"
                f"📱 @{message.from_user.username or '—'}"
            )
        except Exception:
            pass

    await message.answer(
        "✅ Репетитор получил ваш запрос и свяжется с вами в ближайшее время!"
    )


# =================== ПРОСМОТР ЗАПИСЕЙ ===================

@router.callback_query(F.data.startswith("mybooking:") & ~F.data.startswith("mybooking:cancel:"))
async def view_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await callback.answer("Запись не найдена", show_alert=True)
        return

    from utils.helpers import format_date
    from keyboards.student_kb import booking_detail_keyboard

    status_text = {
        "confirmed": "✅ Подтверждена",
        "pending": "⏳ Ожидает",
        "completed": "📗 Завершена",
        "cancelled": "❌ Отменена"
    }.get(booking["status"], "—")

    text = (
        f"📋 **Детали записи #{booking['id']}**\n\n"
        f"📚 Предмет: {booking.get('subject_name', '—')}\n"
        f"📅 Дата: {format_date(booking.get('date', ''))}\n"
        f"🕐 Время: {booking.get('start_time', '')[:5]} — "
        f"{booking.get('end_time', '')[:5]}\n"
        f"📝 Тип: {booking.get('booking_type', '—')}\n"
        f"📌 Статус: {status_text}\n"
    )

    can_cancel = booking["status"] in ("confirmed", "pending")
    await callback.message.edit_text(
        text,
        reply_markup=booking_detail_keyboard(booking_id, can_cancel),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("mybooking:cancel:"))
async def cancel_my_booking(callback: CallbackQuery):
    booking_id = int(callback.data.split(":")[-1])
    await db.cancel_booking(booking_id, "Отменено учеником")
    await callback.answer("❌ Запись отменена", show_alert=True)

    # Уведомляем админа
    booking = await db.get_booking(booking_id)
    student = await db.get_student(callback.from_user.id)
    for admin_id in config.ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"❌ Ученик отменил запись!\n\n"
                f"👤 {student['full_name'] if student else '—'}\n"
                f"📅 Запись #{booking_id}"
            )
        except Exception:
            pass

    await callback.message.edit_text(Texts.BOOKING_CANCELLED)


# =================== ПРОСМОТР ДЗ ===================

@router.callback_query(F.data.startswith("hw:view:"))
async def view_homework(callback: CallbackQuery):
    hw_id = int(callback.data.split(":")[-1])
    hw_list = await db.get_student_homework(callback.from_user.id)
    hw = next((h for h in hw_list if h["id"] == hw_id), None)

    if not hw:
        await callback.answer("ДЗ не найдено", show_alert=True)
        return

    from keyboards.student_kb import hw_detail_keyboard

    status_text = {
        "assigned": "📝 Задано",
        "submitted": "📤 Сдано",
        "graded": "✅ Проверено"
    }.get(hw["status"], "—")

    text = (
        f"📝 **{hw['title']}**\n\n"
        f"📚 Предмет: {hw.get('subject_name', '—')}\n"
        f"📌 Статус: {status_text}\n"
        f"📄 Описание:\n{hw.get('description', '—')}\n"
    )

    if hw.get("due_date"):
        text += f"📅 Сдать до: {hw['due_date']}\n"

    if hw.get("grade"):
        text += f"\n📊 Оценка: {hw['grade']}\n"

    if hw.get("feedback"):
        text += f"💬 Комментарий: {hw['feedback']}\n"

    await callback.message.edit_text(
        text,
        reply_markup=hw_detail_keyboard(hw_id, hw["status"]),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("hw:submit:"))
async def submit_homework(callback: CallbackQuery):
    hw_id = int(callback.data.split(":")[-1])
    await db.submit_homework(hw_id)
    await callback.answer("📤 ДЗ отмечено как сданное!", show_alert=True)

    # Уведомляем админа
    student = await db.get_student(callback.from_user.id)
    for admin_id in config.ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"📤 Ученик сдал ДЗ!\n\n"
                f"👤 {student['full_name'] if student else '—'}\n"
                f"📝 ДЗ #{hw_id}"
            )
        except Exception:
            pass


@router.callback_query(F.data == "hw:list")
async def hw_list_back(callback: CallbackQuery):
    hw_list = await db.get_student_homework(callback.from_user.id)
    if not hw_list:
        await callback.message.edit_text("📭 Домашних заданий нет.")
        return

    from keyboards.student_kb import homework_list_keyboard
    await callback.message.edit_text(
        "📝 **Ваши задания:**",
        reply_markup=homework_list_keyboard(hw_list),
        parse_mode="Markdown"
    )


# =================== ОТЗЫВЫ ===================

@router.callback_query(F.data.startswith("review:rate:"))
async def process_rating(callback: CallbackQuery, state: FSMContext):
    rating = int(callback.data.split(":")[-1])
    await state.update_data(rating=rating)
    await state.set_state(ReviewText.text)
    await callback.message.edit_text(
        f"Ваша оценка: {'⭐' * rating}\n\n"
        f"Напишите отзыв (или отправьте '-' чтобы пропустить):"
    )


@router.message(ReviewText.text)
async def process_review_text(message: Message, state: FSMContext):
    data = await state.get_data()
    text = "" if message.text == "-" else message.text
    review_id = await db.add_review(
        message.from_user.id, data["rating"], text,
        data.get("booking_id")
    )
    await state.clear()
    await message.answer(
        f"Спасибо за отзыв! ❤️\n"
        f"Ваша оценка: {'⭐' * data['rating']}",
        reply_markup=student_main_menu()
    )

    # Уведомляем админа
    student = await db.get_student(message.from_user.id)
    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"⭐ Новый отзыв!\n\n"
                f"👤 {student['full_name'] if student else '—'}\n"
                f"📊 Оценка: {'⭐' * data['rating']}\n"
                f"💬 {text or '(без текста)'}"
            )
        except Exception:
            pass


# =================== АВТООТВЕТ НА ВОПРОСЫ ===================

@router.message(F.text)
async def auto_faq_answer(message: Message):
    """Автоматический ответ на основе FAQ ключевых слов."""
    if message.from_user.id in config.ADMIN_IDS:
        return

    faq = await db.find_faq_answer(message.text)
    if faq:
        await message.answer(
            f"❓ {faq['question']}\n\n"
            f"💬 {faq['answer']}"
        )
    else:
        # Пересылаем вопрос админу
        for admin_id in config.ADMIN_IDS:
            try:
                student = await db.get_student(message.from_user.id)
                name = student["full_name"] if student else message.from_user.full_name
                await message.bot.send_message(
                    admin_id,
                    f"💬 Вопрос от ученика\n\n"
                    f"👤 {name} (@{message.from_user.username or '—'})\n"
                    f"📝 {message.text}"
                )
            except Exception:
                pass

        await message.answer(
            "📩 Ваш вопрос передан репетитору. "
            "Ответ придёт в ближайшее время!"
        )